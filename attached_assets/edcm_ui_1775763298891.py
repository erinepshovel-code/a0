from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.app import App
from kivy.core.clipboard import Clipboard

# --- 1. SMART INPUT CLASS ---
class SmartAuditInput(TextInput):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.use_bubble = True

    def copy(self, data=''):
        """Overrides native copy to handle massive text."""
        selection = self.selection_text
        SIZE_LIMIT = 500 * 1024 

        if len(selection.encode('utf-8')) > SIZE_LIMIT:
            app = App.get_running_app()
            if hasattr(app, 'clipboard_manager'):
                app.clipboard_manager.smart_copy(selection)
        else:
            Clipboard.copy(selection)

# --- 2. MAIN UI LAYOUT ---
class EDCM_UI(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'vertical'
        self.padding = 10
        self.spacing = 5
        
        self.text_visible = True 
        self.inputs = []

        # A. STATUS HEADER
        self.status_header = Label(
            text="EDCM Ready (No Data)", 
            size_hint_y=None, height=40, 
            color=(0.5, 1, 0.5, 1), bold=True
        )
        self.add_widget(self.status_header)

        # B. TOGGLE BUTTON
        self.btn_toggle = Button(
            text="HIDE TEXT ▼", 
            size_hint_y=None, height=40,
            background_color=(0.3, 0.3, 0.3, 1)
        )
        self.btn_toggle.bind(on_press=self.toggle_text_view)
        self.add_widget(self.btn_toggle)

        # C. COLLAPSIBLE TEXT AREA
        self.input_container = BoxLayout(orientation='vertical', spacing=2)
        
        labels = ["Prompt:", "Response A:", "Correction:", "Response B:"]
        for lbl in labels:
            self.input_container.add_widget(Label(text=lbl, size_hint_y=None, height=20, halign='left'))
            inp = SmartAuditInput(
                multiline=True, 
                background_color=(0.15, 0.15, 0.15, 1), 
                foreground_color=(1, 1, 1, 1)
            )
            self.inputs.append(inp)
            self.input_container.add_widget(inp)
            
        self.add_widget(self.input_container)

        # D. ACTION BUTTONS (Updated with LOAD)
        btn_layout = BoxLayout(size_hint_y=None, height=50, spacing=5)
        
        self.btn_prev = Button(text="<", size_hint_x=0.8, background_color=(0.4, 0.4, 0.4, 1))
        
        # NEW: The Master Load Button
        self.btn_load = Button(text="LOAD", background_color=(0.8, 0.5, 0.1, 1))
        
        self.btn_analyze = Button(text="AUDIT", background_color=(0.1, 0.5, 0.8, 1))
        self.btn_copy = Button(text="COPY", background_color=(0.2, 0.6, 0.2, 1))
        
        self.btn_next = Button(text=">", size_hint_x=0.8, background_color=(0.4, 0.4, 0.4, 1))
        
        btn_layout.add_widget(self.btn_prev)
        btn_layout.add_widget(self.btn_load)
        btn_layout.add_widget(self.btn_analyze)
        btn_layout.add_widget(self.btn_copy)
        btn_layout.add_widget(self.btn_next)
        
        self.add_widget(btn_layout)
        
        # Expose exit button for Main to bind if needed, or rely on Android Back
        self.btn_exit = Button(text="X", size_hint_x=0.5, background_color=(0.8, 0.2, 0.2, 1))
        # Optional: Add exit to row if you have space, or leave out.

    def toggle_text_view(self, instance):
        if self.text_visible:
            self.input_container.opacity = 0
            self.input_container.size_hint_y = None
            self.input_container.height = 0
            self.btn_toggle.text = "SHOW TEXT ▲"
            self.text_visible = False
        else:
            self.input_container.opacity = 1
            self.input_container.size_hint_y = 1
            self.btn_toggle.text = "HIDE TEXT ▼"
            self.text_visible = True

    def update_slots(self, text_list):
        for i, text in enumerate(text_list):
            if i < len(self.inputs):
                self.inputs[i].text = text

    def update_header(self, text):
        self.status_header.text = text
