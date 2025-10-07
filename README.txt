1. Put your images/videos in the media/ folder.
2. Edit config.py: set API_ID, API_HASH, and CPA_LINK.
3. (Optional) Run Ollama locally if you want more advanced LLM replies:
   ollama pull artifish/llama3.2-uncensored:latest
   ollama serve
4. Install requirements:
   pip install -r requirements.txt
5. Run:
   python userbot.py
