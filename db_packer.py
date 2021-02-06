#!/bin/python

import sqlite3
import sys
import hashlib
import shutil
import os
import zstd
import lzma

#args
folder = ""
if len(sys.argv) < 2 or sys.argv[1] == None:
	print("No input folder specified. Quitting.")
	quit()

folder = sys.argv[1]
if not os.path.isdir(folder):
	print("Input directory not found.")
	quit()

targetFolder = '/tmp/of'
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

if not os.path.isdir(targetFolder):
	os.makedirs(targetFolder)

print(folder)
print(targetFolder)
print(compression)



def should_skip_file(filename):
	return filename.startswith('.') or subdir[len(folder)::].startswith('.') or filename == 'ofmanifest.db' or filename == 'gameinfo.txt' or filename=='db_packer_fen.py' or filename == os.path.basename(__file__);

dbFilePath = os.path.join(targetFolder, 'ofmanifest.db')

should_create = not os.path.isfile(dbFilePath)

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
			checksumlzma text not null
		)
		""")
skipped = []


for subdir, dirs, files in os.walk(folder):
	for filename in files:
		print("for: " + filename)
		if should_skip_file(filename):
			print("Skipping %s." % filename)
			skipped.append(filename)
			continue

		filepath = os.path.join(subdir,  filename)
		dbpath = filepath[len(folder)::]
		print("%s:" % filepath)

		c.execute('SELECT * FROM files WHERE path=?', (dbpath,) )
		res = c.fetchone()

		if os.stat(filepath).st_size == 0:
			data = bytes()
			#new_sum = 'd41d8cd98f00b204e9800998ecf8427e'
		else:
			data = open(filepath, 'rb').read()
		new_sum = hashlib.md5(data).hexdigest()
		#comp = lzma.LZMACompressor()

		
		#print("MD5 of %s: %s" % (filepath, new_sum))
		if res is None:
			print("Adding %s." % dbpath)

			#compressed = comp.compress(data) + comp.flush()
			#compressed
			if data == bytes():
				print("This file is empty.")
				compressed = data
			else:
				compressed = zstd.compress(data)
			os.makedirs(os.path.dirname(os.path.join(targetFolder,dbpath)), exist_ok=True)
			open(os.path.join(targetFolder,dbpath), 'wb').write(compressed)
			comp_sum = hashlib.md5(compressed).hexdigest()
			
			c.execute('INSERT INTO files VALUES (?,?,?,?)', (dbpath, 0, new_sum, comp_sum))
		else:
			old_sum = res[2]
			if old_sum != new_sum:
				print("Updating %s.\n" % dbpath)

				#compressed
				if data == bytes():
					compressed = data
					print("This file is empty.")
				else:
					compressed = zstd.compress(data)
				os.makedirs(os.path.dirname(os.path.join(targetFolder,dbpath)), exist_ok=True)
				open(os.path.join(targetFolder,dbpath), 'wb').write(compressed)
				comp_sum = hashlib.md5(compressed).hexdigest()

				c.execute('UPDATE files SET revision=revision+1 WHERE path=?', (dbpath,))
				c.execute('UPDATE files SET checksum=? WHERE path=?', (new_sum, dbpath))
				c.execute('UPDATE files SET checksumlzma=? WHERE path=?', (comp_sum, dbpath))
			else:
				print("%s has not changed\n" % dbpath)

c.execute('SELECT * FROM files')
for row in c.fetchall():
	if not os.path.exists(folder + os.sep + row[0]) or row[0][1::] in skipped:
		print("Deleting %s." % row[0])
		c.execute('DELETE FROM files WHERE path=?', (row[0],))

conn.commit()
conn.close()
