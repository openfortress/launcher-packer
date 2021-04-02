const Discord = require('discord.js');
const client = new Discord.Client();

const path = require('path');
const fs = require('fs-extra');

const spawn = require("child_process").spawn;

const config = require("./config.json");

const developerSnowflake = config.developerSnowflake;

const svnPath = config.svnPath;
const prevPath = config.prevPath;

var startMsg = null;
var inProg = false;

client.once('ready', () => {
	console.log('Logged in.');
});

client.on('message', async (msg) => {
	if(msg.content==='.launcher push update') {
		if(! msg.member.roles.cache.has(developerSnowflake)) {
			msg.reply('Only developers can push updates.');
			return;
		}
		if(inProg) {
			msg.channel.send('The process has already started.  Please wait until that is finished.');
			return;
		}
		inProg = true;
		msg.channel.startTyping();
		msg.channel.send('Pushing updates from SVN to launcher repo for public.\n\nWorking!  This will take a while, please be patient.', {files: ["./dig.gif"]}).then(s => {
			startMsg = s;
		});
		msg.channel.stopTyping();

		const svnUpdate = spawn('svn', ['update', svnPath]);

		svnUpdate.stdout.on('data', (data) => {
			console.log(data.toString());
		});

		svnUpdate.stderr.on('data', (data) => {
			console.log('\x1b[31m', data.toString(), '\x1b[0m');
		}); 

		svnUpdate.on('exit', (code, signal) => {
			console.log('Svn update exited with code: ', code);

			if(code != 0) {
				console.log(signal);
				msg.channel.send('Ruh roh, there was an error executing the script.  Ask Fenteale to help.');
				inProg = false;
				return;
			}
			console.log('SVN update success!  Continuing with launcher script.');

			
			const lpScript = spawn('python3', ['./db_packer.py', svnPath, '-p', prevPath, '-k', config.keyPath]);

			lpScript.stdout.on('data', (data) => {
				console.log(data.toString());
			});

			lpScript.stderr.on('data', (data) => {
				console.log('\x1b[31m', data.toString(), '\x1b[0m');
			}); 

			lpScript.on('error', (err) => {
				console.log(err.toString());
				msg.channel.send('Ruh roh, there was an error executing the script.  Ask Fenteale to help.');
			});

			lpScript.on('exit', (code, signal) => {
				console.log('Launcher packer script exited with code: ', code);

				if(startMsg != null)
					startMsg.delete();
				
				if(code != 0) {
					console.log(signal);
					msg.channel.send('Ruh roh, there was an error executing the script.  Ask Fenteale to help.');
					inProg = false;
					return;
				}

				console.log('Ran python script successfully.  Moving files now.');

				fs.rmdirSync(prevPath, { recursive: true });

				fs.moveSync('/tmp/of', prevPath);

				console.log('Everything is done!');

				msg.channel.send('Update is pushed to the launcher repo!');
				inProg = false;
			});
		});

	}
})

client.login(config.discordToken);

