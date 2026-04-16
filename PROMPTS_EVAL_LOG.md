# Cursor Prompt Evaluation Log

This file documents user prompts written in Cursor for home assignment evaluation.

## 2026-04-16

### Prompt 1
Part of a job interview, I need to develop a system that uploads through a web interface docx files, the files are stored and analyzed using AI. The analysis done on the uploaded file is based on set of freetext rules inputed by the user. The goal of these rules is for example to prevent leakage of confidential data. I want you to build me this system as an experienced software engineer but before starting to do that I have couple of guidelines - 1. in the task I'm allowed to use AI agents like cursor 2. EVERY prompt I give should be documented on a designated file 3. External LLM should be used to analyze the data if it corresponds to the rules so there should be an input for API key for the LLM vendor - let's agree that you will create a configuration page to select OPEN AI/CLAUDE (anthropic) and you will allow the user to add the key and you will have a verify button and a save button. any key added afterwards will remove the previous key. 4. before starting to develop code - I would appreciate to work in batches so that you create code and I approve it.

### Prompt 2
regarding batch 3 - the rules should be consistent across all documents so it's not "rules per doc" but rather "rules per system"

### Prompt 3
Build Plan: Global-Rules DOCX Analyzer. Implement the plan as specified, it is attached for your reference. Do NOT edit the plan file itself. To-do's from the plan have already been created. Do not create them again. Mark them as in_progress as you work, starting with the first one. Don't stop until you have completed all the to-dos.

### Prompt 4
comment- for the rules - endpoint wise I want to be able in the interface to remove rules so the API and frontend must support this functionallity

regarding the environment - 
I want to be able to run venv and docker in my wsl commandline

In the meantime - I want to get an MVP before we deal with hardenings

### Prompt 5
It seems that I have a low internet speed - because i'm tight on schedule let's do the following - 1. keep the option for docker deployment 2. create a fallback for a full localhost run outside of the container scope to move things forward

### Prompt 6
so I installed venv and it works but when i run pytest -q it shows an import error

### Prompt 7
when I browse locally to localhost:8000 i get {"detail":"not found"} and in the chrome developer tools i get Request URL http://localhost:8000/ Status Code 404 Not Found

### Prompt 8
I get this error when i'm trying to rerun docker-compose up --build (KeyError: 'ContainerConfig')

### Prompt 9
when i try to apt install docker-compose-plugin I get unable to locate package docker-compose-plugin

### Prompt 10
there are still residues from before - help me clean them up (container name conflict on docs-analyzer-backend)

### Prompt 11
I will run this now but please create a restart script in the repo for quick "reboot" script

### Prompt 12
I'm still getting {"detail":"Not Found"} and a 404 error from the server, maybe the routing external to the containers frontend/backend is not wired correctly

### Prompt 13
connection is refused when i reach the health api, check the terminal for the errors

### Prompt 14
so the interface and seems the backend are up and running. this is a good point to commit, write a detailed message and push to remote.
