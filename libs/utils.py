# libs/utils.py
from datetime import datetime
from kivy.uix.popup import Popup
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.clock import Clock

BG = (0.12, 0.12, 0.18, 1)
FG = (0.80, 0.84, 0.96, 1)
FG2 = (0.65, 0.68, 0.78, 1)
ACCENT = (0.49, 0.42, 0.97, 1)

def format_date(date_str):
    """Format date string for display"""
    if not date_str:
        return 'Never'
    
    try:
        dt = datetime.fromisoformat(date_str)
        now = datetime.now()
        
        delta = now - dt
        
        if delta.days == 0:
            if delta.seconds < 60:
                return 'Just now'
            elif delta.seconds < 3600:
                mins = delta.seconds // 60
                return f'{mins}m ago'
            else:
                hours = delta.seconds // 3600
                return f'{hours}h ago'
        elif delta.days == 1:
            return 'Yesterday'
        elif delta.days < 7:
            return f'{delta.days}d ago'
        else:
            return dt.strftime('%m-%d')
    except:
        return 'Unknown'

def show_toast(message, duration=2):
    """Show a toast notification"""
    toast_popup = Popup(
        title='',
        size_hint=(0.8, 0.1),
        pos_hint={'center_x': 0.5, 'y': 0.05}
    )
    
    content = BoxLayout(orientation='vertical', padding='10dp')
    label = Label(
        text=message,
        color=FG,
        font_size='13sp'
    )
    content.add_widget(label)
    
    toast_popup.content = content
    toast_popup.background_color = (0.2, 0.2, 0.3, 0.9)
    
    toast_popup.open()
    
    Clock.schedule_once(lambda dt: toast_popup.dismiss(), duration)

def send_notification(title, message):
    """Send system notification"""
    try:
        from plyer import notification
        
        notification.notify(
            title=title,
            message=message,
            timeout=10
        )
    except:
        show_toast(f'{title}: {message}')

def is_wifi_connected():
    """Check if connected to WiFi"""
    try:
        from plyer import connectivity
        
        conn_type = connectivity.get_connection_type()
        return conn_type == 'wifi'
    except:
        return True

def is_mobile_data_connected():
    """Check if connected to mobile data"""
    try:
        from plyer import connectivity
        
        conn_type = connectivity.get_connection_type()
        return conn_type in ['mobile', '2g', '3g', '4g', '5g']
    except:
        return False