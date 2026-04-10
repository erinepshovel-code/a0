import re
import os

# --- TOKENIZER ---
_TOKEN_RE = re.compile(r"\b\w+\b|[\^\w\s]", re.UNICODE)

def tokenize(text: str):
    """Fast tokenizer for mobile."""
    if not text or not isinstance(text, str):
        return []
    return _TOKEN_RE.findall(text.lower())

# --- LARGE CLIPBOARD MANAGER ---
import threading
from kivy.core.clipboard import Clipboard
from kivy.clock import Clock

class LargeClipboardManager:
    def __init__(self):
        self.SIZE_LIMIT = 500 * 1024 
        self.CACHE_FILE = "edcm_clipboard_dump.txt"

    def smart_copy(self, text, callback=None):
        threading.Thread(target=self._copy_logic, args=(text, callback)).start()

    def _copy_logic(self, text, callback):
        data_size = len(text.encode('utf-8'))
        message = ""

        if data_size < self.SIZE_LIMIT:
            Clock.schedule_once(lambda dt: Clipboard.copy(text), 0)
            message = f"Copied {data_size} bytes."
        else:
            try:
                with open(self.CACHE_FILE, "w", encoding="utf-8") as f:
                    f.write(text)
                snippet = text[:100] + "\n... [Saved to file]"
                Clock.schedule_once(lambda dt: Clipboard.copy(snippet), 0)
                message = f"Too large! Saved to {self.CACHE_FILE}"
            except Exception as e:
                message = f"Error: {str(e)}"

        if callback:
            Clock.schedule_once(lambda dt: callback(message), 0)

# --- ACCREDITATION PARSER (Folder Capable) ---
class AccreditationParser:
    def __init__(self):
        # The Filter: Distinguishes Metadata from Text Blocks
        # Matches: "Name:", "[Name]:", "Name >>", "[Time] Name:"
        self.meta_pattern = re.compile(r"^\[?.*?\]?\s*([A-Za-z0-9 _\.]+)(:|>>|\])\s*$")

    def ingest(self, path):
        """
        Ingests a single file OR a folder of files.
        Returns a unified list of speech acts.
        """
        master_transcript = []

        # 1. Check if it's a Folder
        if os.path.isdir(path):
            # Sort files to ensure chronological order if named correctly (01.txt, 02.txt)
            for filename in sorted(os.listdir(path)):
                if filename.endswith((".txt", ".log", ".md")):
                    full_path = os.path.join(path, filename)
                    # Append file marker so you know a new file started
                    master_transcript.append({
                        "source": "SYSTEM", 
                        "text": f"--- FILE START: {filename} ---"
                    })
                    master_transcript.extend(self._process_file(full_path))
        
        # 2. Check if it's a File
        elif os.path.isfile(path):
            master_transcript = self._process_file(path)
            
        else:
            return []

        return master_transcript

    def _process_file(self, filepath):
        """Internal worker that applies the Metadata Rules to one file."""
        transcript = []
        current_source = "Unattributed"
        current_buffer = []

        try:
            with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
                lines = f.readlines()
        except Exception:
            return []

        for line in lines:
            stripped = line.strip()
            match = self.meta_pattern.match(stripped)
            
            # --- THE KEY DISTINCTION LOGIC ---
            # It is Metadata IF:
            # 1. It matches the regex pattern (Name:)
            # 2. AND it is short (< 50 chars)
            # 3. AND it is not just a sentence that happens to have a colon
            if match and len(stripped) < 50:
                # COMMIT PREVIOUS BLOCK
                if current_buffer or current_source != "Unattributed":
                    transcript.append({
                        "source": current_source,
                        "text": "\n".join(current_buffer).strip()
                    })
                
                # SWITCH SOURCE (Metadata Found)
                current_source = match.group(1).strip()
                current_buffer = []
            else:
                # IT IS TEXT BLOCK
                if stripped:
                    current_buffer.append(stripped)

        # Commit final block
        if current_buffer:
            transcript.append({
                "source": current_source,
                "text": "\n".join(current_buffer).strip()
            })
            
        return transcript

# --- CONVERSATION ENGINE ---
class ConversationEngine:
    def __init__(self):
        self.history = [] 
        self.current_index = 0

    def load_data(self, transcript_list):
        self.history = transcript_list
        self.current_index = 0
        
    def get_view_window(self):
        view = []
        for i in range(4):
            target_idx = self.current_index + i
            if target_idx < len(self.history):
                entry = self.history[target_idx]
                view.append(f"{entry['source']}:\n{entry['text']}")
            else:
                view.append("") 
        return view

    def scroll(self, direction):
        new_index = self.current_index + direction
        if 0 <= new_index < len(self.history):
            self.current_index = new_index
            return True
        return False
