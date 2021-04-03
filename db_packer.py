#!/bin/python3

import sqlite3
import sys
import shutil
import os
import zstd
import lzma
from Crypto.Hash import SHA384
from Crypto.PublicKey import RSA
from Crypto.Signature import pkcs1_15

# args
folder = ""
key = None
if len(sys.argv) < 2 or sys.argv[1] == None:
    print("No input folder specified. Quitting.")
    quit()

if sys.argv[1] == "--help" or sys.argv[1] == "-h":
    print("USAGE")
    print("\tdb_packer.py [INPUT DIRECTORY] -k [KEY]... [OPTIONS]...\n")
    print("OPTIONS\n")
    print("\tINPUT DIRECTORY is the directory where the svn repository, or other")
    print("\trepository folder for the game files are stored.\n")
    print("\tKEY is an RSA private key in a .pem file format. Used for signing")
    print("\tbinaries to prevent tampering..\n")
    print("\t-o [OUTPUT FOLDER]")
    print("\t\tDirectory where to write the compressed files and database.")
    print("\t\tBy default this is /tmp/of\n")
    print("\t-c [COMPRESSION METHOD]")
    print("\t\tCompression to use, this can be zstd or lzma.  Default is zstd.\n")
    print("\t-p [PREVIOUS OUTPUT DIRECTORY]")
    print("\t\tDirectory that contains the previous version of the compressed")
    print("\t\tfiles to compare against for generating file revisions.")
    quit()

folder = sys.argv[1]
if not os.path.isdir(folder):
    print("Input directory not found.")
    quit()

targetFolder = '/tmp/of'
previousFolder = '/var/www/html/zstd'
compression = 'zstd'

for a_i in range(2, len(sys.argv)):
    if sys.argv[a_i] == "-o":
        if len(sys.argv) < a_i + 2:
            print("No output directory specified.  Quitting.")
            quit()
        targetFolder = sys.argv[a_i + 1]
        if not os.path.isdir(targetFolder):
            print("Output directory could not be created.  Quitting")
            quit()
    elif sys.argv[a_i] == "-c":
        if len(sys.argv) < a_i + 2:
            print("No compression method specified.  Quitting.")
            quit()
        compression = sys.argv[a_i + 1].lower()
        if compression != 'zstd' and compression != 'lzma':
            print("Compression method not recognized.  Quitting")
            quit()
    elif sys.argv[a_i] == "-p":
        if len(sys.argv) < a_i + 2:
            print("No previous output directory specified.  Quitting.")
            quit()
        previousFolder = sys.argv[a_i + 1]
        if not os.path.isdir(previousFolder):
            print("Previous directory not found.  Quitting")
            quit()
    elif sys.argv[a_i] == '-k':
        if len(sys.argv) < a_i + 2:
            print("No private key specified.  Quitting.")
            quit()
        key_file = sys.argv[a_i + 1]
        if not os.path.isfile(key_file):
            print("Key file not found.  Quitting")
            quit()
        key = RSA.import_key(open(key_file).read())

if (os.path.isdir(targetFolder)):
    shutil.rmtree(targetFolder)
os.makedirs(targetFolder)

print(folder)
print(targetFolder)
print(previousFolder)
print(compression)


def should_skip_file(filename):
    return filename.startswith('.') or subdir[len(folder)::].startswith(
        '.') or filename == 'ofmanifest.db' or filename == 'gameinfo.txt' or filename == 'db_packer_fen.py' or filename == os.path.basename(
        __file__);


# dbFilePath = os.path.join(targetFolder, 'ofmanifest.db')
dbFilePath = os.path.join(previousFolder, 'ofmanifest.db')

should_create = not os.path.isfile(dbFilePath)
dbFilePathL = os.path.join(targetFolder, 'ofmanifest.db')
if not should_create:
    shutil.copy(dbFilePath, dbFilePathL)

dbFilePath = dbFilePathL

print(dbFilePath)
conn = sqlite3.connect(dbFilePath)
c = conn.cursor()
if should_create:
    c.execute(
        """
        CREATE TABLE files
        (
            path text not null constraint files_pk primary key,
            revision int not null,
            checksum text not null,
            checksumlzma text not null,
            signature text
        )
        """)
else:
    x = [col[1] for col in c.execute('PRAGMA table_info(files)')]
    if "signature" not in x:
        c.execute("ALTER TABLE files ADD COLUMN signature;")
skipped = []

for subdir, dirs, files in os.walk(folder):
    for filename in files:
        ##print("for: " + filename)
        if should_skip_file(filename):
            ##print("Skipping %s." % filename)
            skipped.append(filename)
            continue

        filepath = os.path.join(subdir, filename)
        dbpath = filepath[len(folder)::]
        ##print("%s:" % filepath)

        c.execute('SELECT * FROM files WHERE path=?', (dbpath,))
        res = c.fetchone()

        if os.stat(filepath).st_size == 0:
            data = bytes()
        else:
            data = open(filepath, 'rb').read()
        sign_sum = SHA384.new(data)
        new_sum = sign_sum.hexdigest()

        if compression == "lzma":
            comp = lzma.LZMACompressor()

        # print("MD5 of %s: %s" % (filepath, new_sum))
        if res is None:
            ##print("Adding %s." % dbpath)
            if compression == "zstd":
                if data == bytes():
                    print("This file is empty.")
                    compressed = data
                else:
                    compressed = zstd.compress(data)
            os.makedirs(os.path.dirname(os.path.join(targetFolder, dbpath)), exist_ok=True)
            open(os.path.join(targetFolder, dbpath), 'wb').write(compressed)
            comp_sum = SHA384.new(compressed).hexdigest()
            if ".dll" in dbpath or ".so" in dbpath or ".cfg" in dbpath:
                print("Signing...")
                signature = pkcs1_15.new(key).sign(sign_sum)
            else:
                signature = None
            c.execute('INSERT INTO files VALUES (?,?,?,?,?)', (dbpath, 0, new_sum, comp_sum,signature))
        else:
            old_sum = res[2]
            if old_sum != new_sum:
                print("Updating %s.\n" % dbpath)
                if compression == "zstd":
                    if data == bytes():
                        ##print("This file is empty.")
                        compressed = data
                    else:
                        compressed = zstd.compress(data)

                os.makedirs(os.path.dirname(os.path.join(targetFolder, dbpath)), exist_ok=True)
                open(os.path.join(targetFolder, dbpath), 'wb').write(compressed)
                comp_sum = SHA384.new(compressed).hexdigest()
                if ".dll" in dbpath or ".so" in dbpath or ".cfg" in dbpath:
                    print("Updating signature...")
                    signature = pkcs1_15.new(key).sign(sign_sum)
                else:
                    signature = None
                c.execute('UPDATE files SET revision=revision+1 WHERE path=?', (dbpath,))
                c.execute('UPDATE files SET checksum=? WHERE path=?', (new_sum, dbpath))
                c.execute('UPDATE files SET checksumlzma=? WHERE path=?', (comp_sum, dbpath))
                c.execute('UPDATE files SET signature=? WHERE path=?', (signature, dbpath))
            else:
                print("%s has not changed\n" % dbpath)
                os.makedirs(os.path.dirname(os.path.join(targetFolder, dbpath)), exist_ok=True)
                shutil.copy(os.path.join(previousFolder, dbpath), os.path.join(targetFolder, dbpath))

c.execute('SELECT * FROM files')
for row in c.fetchall():
    if not os.path.exists(os.path.join(folder, row[0])) or row[0][1::] in skipped:
        print("Deleting %s." % row[0])
        c.execute('DELETE FROM files WHERE path=?', (row[0],))

conn.commit()
conn.close()
db = open(targetFolder+"/ofmanifest.db",'rb')
dbr = db.read()
dbsum = pkcs1_15.new(key).sign(SHA384.new(dbr))
db.close()
ds = open(targetFolder+"/ofmanifest.sig",'wb')
ds.write(dbsum)
ds.close()


