from gtts import gTTS
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import os
from pathlib import Path
import pygame
import time
import requests
import sys
import tempfile

class TextEntry:
    def __init__(self, parent_frame, index, default_save_path, app_instance):
        self.app = app_instance # Reference to the main application instance
        self.frame = ttk.Frame(parent_frame)
        self.frame.pack(fill=tk.X, pady=5, padx=5)

        # Text input (allow vertical expansion)
        self.text_input = tk.Text(self.frame, height=3, width=45, font=("Arial", 11), wrap=tk.WORD)
        self.text_input.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))

        # Right-side controls frame
        controls_frame = ttk.Frame(self.frame)
        controls_frame.pack(side=tk.LEFT, fill=tk.Y)

        # --- Filename and Browse ---
        file_frame = ttk.Frame(controls_frame)
        file_frame.pack(fill=tk.X, pady=(0, 2))

        # Default to .mp3 extension for gTTS
        default_filename = os.path.join(default_save_path, f"output_{index+1}.mp3")
        self.filename_var = tk.StringVar(value=default_filename)
        self.filename_entry = ttk.Entry(file_frame, textvariable=self.filename_var, width=25)
        self.filename_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))

        self.browse_button = ttk.Button(file_frame, text="...", width=3, # Compact browse button
                                      command=lambda: self.browse_location(default_save_path))
        self.browse_button.pack(side=tk.LEFT)

        # --- Action Buttons (Preview, Remove) ---
        action_frame = ttk.Frame(controls_frame)
        action_frame.pack(fill=tk.X, pady=(2,0))

        self.preview_button = ttk.Button(action_frame, text="Preview", width=8,
                                       command=self.preview_audio)
        self.preview_button.pack(side=tk.LEFT, padx=(0, 5))

        self.remove_button = ttk.Button(action_frame, text="Remove", width=8,
                                      command=lambda: self.remove_entry(parent_frame))
        self.remove_button.pack(side=tk.LEFT)

    def browse_location(self, default_save_path):
        try:
            filename = filedialog.asksaveasfilename(
                defaultextension=".mp3",
                filetypes=[("MP3 files", "*.mp3")],
                initialdir=os.path.dirname(self.filename_var.get()) or default_save_path,
                initialfile=os.path.basename(self.filename_var.get())
            )
            if filename:
                self.filename_var.set(filename)
        except Exception as e:
            messagebox.showerror("Error", f"Error selecting file: {str(e)}")

    def remove_entry(self, parent_frame):
        """Removes this TextEntry from the UI and the application's list."""
        try:
            if self in self.app.text_entries:
                self.app.text_entries.remove(self)
            self.frame.destroy()
            parent_frame.update_idletasks()
        except Exception as e:
            messagebox.showerror("Error", f"Error removing entry: {str(e)}")

    def preview_audio(self):
        """Requests the main app to preview audio for this entry."""
        text = self.text_input.get("1.0", tk.END).strip()
        if not text:
            messagebox.showwarning("Preview", "Please enter some text to preview.")
            return
        self.preview_button.config(state=tk.DISABLED)
        self.app.preview_text(text, self.preview_button)
        # Re-enable handled by the app after preview finishes

class EnhancedTextToSpeech:
    def __init__(self, root):
        self.root = root
        self.root.title("gTTS Text-to-Speech Converter")
        self.root.geometry("850x650")
        self.root.minsize(700, 500)
        self.root.configure(bg="#e0e0e0")

        style = ttk.Style()
        style.theme_use('clam')
        style.configure("TFrame", background="#e0e0e0")
        style.configure("TLabel", background="#e0e0e0", font=("Arial", 11))
        style.configure("TButton", font=("Arial", 10))
        style.configure("TEntry", font=("Arial", 11))
        style.configure("TCombobox", font=("Arial", 11))
        style.configure("Header.TLabel", font=("Arial", 14, "bold"))

        # Preview state variables
        self.preview_audio_path = None
        self.preview_thread = None
        self.preview_active = False

        # Initialize pygame for audio playback
        try:
            pygame.mixer.init()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to initialize audio: {str(e)}")
            sys.exit(1)
        
        # Set default save location to Downloads folder
        self.default_save_path = str(Path.home() / "Downloads")
        if not os.path.exists(self.default_save_path):
            os.makedirs(self.default_save_path, exist_ok=True)
        
        # Language dictionary with common languages
        self.languages = {
            "English": "en",
            "Korean": "ko",
            "Japanese": "ja",
            "Chinese (Simplified)": "zh-cn",
            "Spanish": "es",
            "French": "fr",
            "German": "de",
            "Italian": "it",
            "Russian": "ru",
            "Portuguese": "pt"
        }
        
        self.text_entries = []
        self.setup_ui()
        
    def check_internet_connection(self):
        try:
            requests.get("http://www.google.com", timeout=5)
            return True
        except requests.RequestException:
            return False
        
    def setup_ui(self):
        settings_frame = ttk.Frame(self.root, padding="10 10 10 5")
        settings_frame.pack(fill=tk.X, side=tk.TOP)
        settings_frame.columnconfigure(1, weight=1)

        header_text = "gTTS Voice Settings"
        ttk.Label(settings_frame, text=header_text, style="Header.TLabel").grid(row=0, column=0, columnspan=3, pady=(0, 10), sticky="w")

        # Language Selection
        ttk.Label(settings_frame, text="Language:").grid(row=1, column=0, padx=(0, 5), pady=(5,0), sticky="w")
        self.language_var = tk.StringVar(value="English")
        self.language_dropdown = ttk.Combobox(settings_frame, textvariable=self.language_var,
                                              values=list(self.languages.keys()), state="readonly", width=20)
        self.language_dropdown.grid(row=1, column=1, padx=(0, 20), pady=(5,0), sticky="ew")

        # Speed Selection
        ttk.Label(settings_frame, text="Speed:").grid(row=2, column=0, padx=(0, 5), pady=(5,0), sticky="w")
        self.speed_var = tk.StringVar(value="Normal")
        speed_frame = ttk.Frame(settings_frame)
        speed_frame.grid(row=2, column=1, sticky="w", pady=(5,0))
        ttk.Radiobutton(speed_frame, text="Normal", variable=self.speed_var, value="Normal").pack(side=tk.LEFT, padx=(0, 10))
        ttk.Radiobutton(speed_frame, text="Slow", variable=self.speed_var, value="Slow").pack(side=tk.LEFT)

        # Main scrollable area
        main_area = ttk.Frame(self.root, padding="10 0 10 10")
        main_area.pack(fill=tk.BOTH, expand=True)
        canvas = tk.Canvas(main_area, bg="#e0e0e0", highlightthickness=0)
        scrollbar = ttk.Scrollbar(main_area, orient="vertical", command=canvas.yview)
        self.scrollable_frame = ttk.Frame(canvas)
        self.scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        self.root.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), "units"))
        canvas_window = canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        def frame_width(event): canvas.itemconfig(canvas_window, width=event.width)
        canvas.bind('<Configure>', frame_width)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.entries_container = ttk.Frame(self.scrollable_frame)
        self.entries_container.pack(fill=tk.X, expand=True)

        # Bottom frame with controls
        bottom_frame = ttk.Frame(self.root, padding="10 5 10 10")
        bottom_frame.pack(fill=tk.X, side=tk.BOTTOM)
        add_button = ttk.Button(bottom_frame, text="Add Text Entry", command=self.add_text_entry)
        add_button.pack(side=tk.LEFT, padx=(0, 20))
        convert_button = ttk.Button(bottom_frame, text="Convert & Save All", command=self.start_conversion_all)
        convert_button.pack(side=tk.LEFT)
        
        # Progress bar
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(bottom_frame, variable=self.progress_var, maximum=100, length=300)
        self.progress_bar.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(20, 0))
        
        # Add initial text entry
        self.add_text_entry()
    
    def add_text_entry(self):
        try:
            entry = TextEntry(self.entries_container, len(self.text_entries), self.default_save_path, self)
            self.text_entries.append(entry)
            self.scrollable_frame.update_idletasks()
        except Exception as e:
            messagebox.showerror("Error", f"Error adding text entry: {str(e)}")
    
    def preview_text(self, text, preview_button):
        """Generate and play a preview of the TTS audio"""
        if self.preview_active:
            # Cancel any existing preview
            self.stop_preview()
            
        self.preview_active = True
        self.preview_thread = threading.Thread(
            target=self._generate_and_play_preview,
            args=(text, preview_button),
            daemon=True
        )
        self.preview_thread.start()
    
    def _generate_and_play_preview(self, text, preview_button):
        """Generate and play preview in a separate thread"""
        try:
            # Check internet connection first
            if not self.check_internet_connection():
                self.root.after(0, lambda: messagebox.showerror(
                    "Preview Error", "No internet connection. Please check your connection."))
                self.root.after(0, lambda: preview_button.config(state=tk.NORMAL))
                self.preview_active = False
                return
            
            # Create temp file for the preview
            temp_dir = tempfile.gettempdir()
            temp_file = os.path.join(temp_dir, "gtts_preview.mp3")
            
            # Create the TTS object
            language_code = self.languages[self.language_var.get()]
            speed_slow = (self.speed_var.get() == "Slow")
            tts = gTTS(text=text, lang=language_code, slow=speed_slow)
            
            # Save to temp file
            tts.save(temp_file)
            self.preview_audio_path = temp_file
            
            # Play the audio
            pygame.mixer.music.load(temp_file)
            pygame.mixer.music.play()
            
            # Wait for playback to finish or be stopped
            while pygame.mixer.music.get_busy() and self.preview_active:
                time.sleep(0.1)
                
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Preview Error", f"Failed to generate preview: {str(e)}"))
        finally:
            # Clean up and restore the UI
            self.preview_active = False
            self.root.after(0, lambda: preview_button.config(state=tk.NORMAL))
    
    def stop_preview(self):
        """Stop any currently playing preview"""
        self.preview_active = False
        if pygame.mixer.music.get_busy():
            pygame.mixer.music.stop()
    
    def start_conversion_all(self):
        if not self.check_internet_connection():
            messagebox.showerror("Error", "No internet connection. Please check your connection and try again.")
            return
            
        # Check if there are any text entries
        if not self.text_entries:
            messagebox.showwarning("Warning", "Please add at least one text entry.")
            return
        
        # Validate all entries
        valid_entries_data = []
        for i, entry in enumerate(self.text_entries):
            text = entry.text_input.get("1.0", tk.END).strip()
            filename = entry.filename_var.get().strip()
            if not text: 
                messagebox.showwarning("Warning", f"Entry #{i+1} has no text.")
                return
            if not filename: 
                messagebox.showwarning("Warning", f"Entry #{i+1} has no filename.")
                return
            
            # Check if the filename contains a valid path
            try:
                dir_path = os.path.dirname(os.path.abspath(filename))
                os.makedirs(dir_path, exist_ok=True)
            except Exception as e:
                messagebox.showerror("Error", f"Invalid filename path for entry #{i+1}: {str(e)}")
                return
                
            valid_entries_data.append({"text": text, "filename": filename, "id": i})
        
        # Start conversion in a separate thread
        self.progress_var.set(0)
        threading.Thread(target=self.convert_all_texts, args=(valid_entries_data,), daemon=True).start()
    
    def convert_all_texts(self, entries_data):
        try:
            total_entries = len(entries_data)
            success_count = 0
            
            for i, data in enumerate(entries_data):
                text, filename, entry_id = data["text"], data["filename"], data["id"]
                
                # Update progress
                progress = ((i) / total_entries) * 100
                self.root.after(0, lambda p=progress: self.progress_var.set(p))
                
                # Convert text to speech
                language_code = self.languages[self.language_var.get()]
                speed_slow = (self.speed_var.get() == "Slow")
                tts = gTTS(text=text, lang=language_code, slow=speed_slow)
                
                # Ensure the directory exists
                os.makedirs(os.path.dirname(os.path.abspath(filename)), exist_ok=True)
                
                # Save with retry mechanism
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        tts.save(filename)
                        success_count += 1
                        break
                    except Exception as e:
                        if attempt == max_retries - 1:
                            self.root.after(0, lambda: messagebox.showerror(
                                "Conversion Error", 
                                f"Failed to save entry #{entry_id+1}: {str(e)}"
                            ))
                        time.sleep(1)
                
                # Update progress after each file
                progress = ((i + 1) / total_entries) * 100
                self.root.after(0, lambda p=progress: self.progress_var.set(p))
            
            # Final status update
            final_progress = 100 if success_count == total_entries else self.progress_var.get()
            self.root.after(0, lambda: self.progress_var.set(final_progress))
            
            if success_count == total_entries:
                self.root.after(0, lambda: messagebox.showinfo("Success", f"{success_count} file(s) saved!"))
            elif success_count > 0:
                self.root.after(0, lambda: messagebox.showwarning("Partial Success", f"{success_count}/{total_entries} file(s) saved."))
            else:
                self.root.after(0, lambda: messagebox.showerror("Failure", "No files were saved."))
            
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", f"An error occurred: {str(e)}"))
            self.root.after(0, lambda: self.progress_var.set(0))

if __name__ == "__main__":
    try:
        root = tk.Tk()
        app = EnhancedTextToSpeech(root)
        root.mainloop()
    except Exception as e:
        messagebox.showerror("Error", f"Application failed to start: {str(e)}")
        sys.exit(1)