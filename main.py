# main.py
import kivy
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.image import AsyncImage
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.textinput import TextInput
from kivy.uix.spinner import Spinner
from kivy.uix.checkbox import CheckBox
from kivy.uix.progressbar import ProgressBar
from kivy.uix.switch import Switch
from kivy.clock import Clock, mainthread
from kivy.core.window import Window
from kivy.uix.floatlayout import FloatLayout

import threading
import json
import os
from pathlib import Path
from datetime import datetime
import subprocess
import time

from libs import config_manager, downloader, utils

# Color Scheme
BG = (0.12, 0.12, 0.18, 1)
BG2 = (0.16, 0.16, 0.24, 1)
BG3 = (0.19, 0.19, 0.27, 1)
ACCENT = (0.49, 0.42, 0.97, 1)
FG = (0.80, 0.84, 0.96, 1)
FG2 = (0.65, 0.68, 0.78, 1)
GREEN = (0, 0.78, 0.32, 1)
RED = (0.95, 0.54, 0.66, 1)
YELLOW = (0.98, 0.89, 0.69, 1)
ORANGE = (0.98, 0.72, 0.53, 1)

Window.size = (1080, 1920)

class DownloadProgressTracker:
    """Track download progress"""
    def __init__(self, total=100):
        self.total = total
        self.current = 0
        self.current_file = ""
        self.speed = "0 B/s"
        self.eta = "00:00"
        self.status = "Preparing..."
        self.is_downloading = False
    
    def update(self, current, total, file_name="", speed="", eta=""):
        self.current = current
        self.total = total
        self.current_file = file_name
        self.speed = speed
        self.eta = eta
        self.is_downloading = True
    
    def complete(self):
        self.is_downloading = False
        self.current = self.total
        self.status = "Complete"
    
    def get_progress_percent(self):
        if self.total == 0:
            return 0
        return (self.current / self.total) * 100


class ObserveEntry:
    """Single observe entry for a channel"""
    def __init__(self, channel_data):
        self.channel_data = channel_data
        self.name = channel_data.get("name", "")
        self.url = channel_data.get("url", "")
        self.enabled = channel_data.get("enabled", True)
        self.new_count = channel_data.get("new_count", 0)
        self.last_checked = channel_data.get("last_checked", None)
        self.thumbnail = channel_data.get("thumbnail_url", "")
        self.videos = []


class ChannelRow(BoxLayout):
    """Custom widget for a single channel in the observe list"""
    def __init__(self, observe_entry, on_observe, on_edit, on_long_press, **kwargs):
        super().__init__(orientation='horizontal', size_hint_y=None, height='120dp', **kwargs)
        
        self.observe_entry = observe_entry
        self.on_observe = on_observe
        self.on_edit = on_edit
        self.on_long_press = on_long_press
        
        from kivy.graphics import Color, Rectangle
        self.canvas.before.clear()
        with self.canvas.before:
            Color(*BG2)
            Rectangle(size=self.size, pos=self.pos)
        
        # Thumbnail
        thumb_box = BoxLayout(size_hint_x=0.25, padding='5dp')
        if observe_entry.thumbnail:
            img = AsyncImage(
                source=observe_entry.thumbnail,
                size_hint=(1, 1)
            )
            thumb_box.add_widget(img)
        else:
            placeholder = Label(
                text='[No\nImage]',
                color=FG2,
                markup=True,
                font_size='10sp'
            )
            thumb_box.add_widget(placeholder)
        
        self.add_widget(thumb_box)
        
        # Channel Info
        info_box = BoxLayout(orientation='vertical', size_hint_x=0.5, padding='10dp', spacing='5dp')
        
        title_label = Label(
            text=observe_entry.name[:25],
            size_hint_y=0.4,
            color=FG,
            bold=True,
            font_size='16sp'
        )
        info_box.add_widget(title_label)
        
        url_label = Label(
            text=observe_entry.url[:40] + '...' if len(observe_entry.url) > 40 else observe_entry.url,
            size_hint_y=0.3,
            color=FG2,
            font_size='10sp'
        )
        info_box.add_widget(url_label)
        
        status_text = f"Last: {utils.format_date(observe_entry.last_checked)}"
        status_color = FG2
        if observe_entry.new_count > 0:
            status_text = f"⚡ {observe_entry.new_count} NEW"
            status_color = ORANGE
        
        status_label = Label(
            text=status_text,
            size_hint_y=0.3,
            color=status_color,
            font_size='12sp',
            bold=observe_entry.new_count > 0
        )
        info_box.add_widget(status_label)
        
        self.add_widget(info_box)
        
        # Action Buttons
        btn_box = BoxLayout(orientation='vertical', size_hint_x=0.25, spacing='5dp', padding='5dp')
        
        observe_btn = Button(
            text='[b]CHECK[/b]' if observe_entry.enabled else '[b]OFF[/b]',
            background_color=ACCENT if observe_entry.enabled else (0.5, 0.5, 0.5, 1),
            markup=True,
            size_hint_y=0.5
        )
        observe_btn.bind(on_press=lambda x: self.on_observe(observe_entry))
        btn_box.add_widget(observe_btn)
        
        edit_btn = Button(
            text='⚙',
            background_color=BG3,
            size_hint_y=0.5
        )
        edit_btn.bind(on_press=lambda x: self.on_edit(observe_entry))
        btn_box.add_widget(edit_btn)
        
        self.add_widget(btn_box)
        
        self.bind(on_touch_down=self._on_touch)
        self.press_time = 0
    
    def _on_touch(self, touch):
        if self.collide_point(*touch.pos):
            if touch.is_double_tap:
                self.on_long_press(self.observe_entry)


class DownloadProgressPopup(Popup):
    """Show download progress"""
    def __init__(self, channel_name, **kwargs):
        super().__init__(
            title=f'Downloading: {channel_name}',
            size_hint=(0.95, 0.6),
            **kwargs
        )
        
        self.channel_name = channel_name
        self.tracker = DownloadProgressTracker()
        
        content = BoxLayout(orientation='vertical', padding='15dp', spacing='10dp')
        
        self.file_label = Label(
            text='Preparing...',
            color=FG,
            size_hint_y=0.2,
            font_size='12sp'
        )
        content.add_widget(self.file_label)
        
        self.progress_bar = ProgressBar(
            max=100,
            value=0,
            size_hint_y=0.15
        )
        content.add_widget(self.progress_bar)
        
        stats_box = BoxLayout(orientation='horizontal', size_hint_y=0.15, spacing='10dp')
        
        self.speed_label = Label(
            text='Speed: 0 B/s',
            color=FG2,
            font_size='11sp'
        )
        stats_box.add_widget(self.speed_label)
        
        self.eta_label = Label(
            text='ETA: --:--',
            color=FG2,
            font_size='11sp'
        )
        stats_box.add_widget(self.eta_label)
        
        content.add_widget(stats_box)
        
        self.percent_label = Label(
            text='0%',
            color=ACCENT,
            size_hint_y=0.15,
            font_size='18sp',
            bold=True
        )
        content.add_widget(self.percent_label)
        
        self.status_label = Label(
            text='Starting download...',
            color=FG2,
            size_hint_y=0.2,
            font_size='11sp'
        )
        content.add_widget(self.status_label)
        
        close_btn = Button(
            text='Hide',
            background_color=BG3,
            size_hint_y=0.15
        )
        close_btn.bind(on_press=self.dismiss)
        content.add_widget(close_btn)
        
        self.content = content
        
        self.update_event = Clock.schedule_interval(self.update_progress, 0.5)
    
    @mainthread
    def update_progress(self, dt):
        """Update progress display"""
        if not self.tracker.is_downloading:
            self.update_event.cancel()
            return
        
        percent = self.tracker.get_progress_percent()
        self.progress_bar.value = percent
        self.percent_label.text = f'{int(percent)}%'
        self.file_label.text = f'File: {self.tracker.current_file[:50]}'
        self.speed_label.text = f'Speed: {self.tracker.speed}'
        self.eta_label.text = f'ETA: {self.tracker.eta}'
        self.status_label.text = self.tracker.status
    
    def on_dismiss(self):
        """Cancel update event"""
        try:
            self.update_event.cancel()
        except:
            pass


class ObserveListScreen(BoxLayout):
    """Main observe list screen"""
    def __init__(self, app, **kwargs):
        super().__init__(orientation='vertical', **kwargs)
        self.app = app
        
        from kivy.graphics import Color, Rectangle
        self.canvas.before.clear()
        with self.canvas.before:
            Color(*BG)
            Rectangle(size=self.size, pos=self.pos)
        
        # Header
        header = BoxLayout(orientation='horizontal', size_hint_y=0.1, padding='10dp', spacing='10dp')
        header.canvas.before.clear()
        with header.canvas.before:
            Color(*BG2)
            Rectangle(size=header.size, pos=header.pos)
        
        title = Label(
            text='[b]▼ YouTube Observe[/b]',
            color=ACCENT,
            markup=True,
            size_hint_x=0.4,
            font_size='22sp'
        )
        header.add_widget(title)
        
        refresh_label = Label(
            text='Auto:',
            color=FG2,
            size_hint_x=0.2,
            font_size='12sp'
        )
        header.add_widget(refresh_label)
        
        self.refresh_switch = Switch(
            active=app.auto_refresh_enabled,
            size_hint_x=0.15
        )
        self.refresh_switch.bind(active=self.toggle_auto_refresh)
        header.add_widget(self.refresh_switch)
        
        refresh_btn = Button(
            text='⟲',
            background_color=ACCENT,
            size_hint_x=0.1
        )
        refresh_btn.bind(on_press=self.refresh_channels)
        header.add_widget(refresh_btn)
        
        add_btn = Button(
            text='+',
            background_color=GREEN,
            size_hint_x=0.1
        )
        add_btn.bind(on_press=self.show_add_channel)
        header.add_widget(add_btn)
        
        self.add_widget(header)
        
        # Sub-header with settings
        settings_bar = BoxLayout(orientation='horizontal', size_hint_y=0.08, padding='10dp', spacing='10dp')
        settings_bar.canvas.before.clear()
        with settings_bar.canvas.before:
            Color(*BG3)
            Rectangle(size=settings_bar.size, pos=settings_bar.pos)
        
        wifi_label = Label(
            text='WiFi Only:',
            color=FG2,
            size_hint_x=0.35,
            font_size='11sp'
        )
        settings_bar.add_widget(wifi_label)
        
        self.wifi_only_switch = Switch(
            active=app.wifi_only_mode,
            size_hint_x=0.15
        )
        self.wifi_only_switch.bind(active=self.toggle_wifi_only)
        settings_bar.add_widget(self.wifi_only_switch)
        
        interval_label = Label(
            text='Check every:',
            color=FG2,
            size_hint_x=0.2,
            font_size='11sp'
        )
        settings_bar.add_widget(interval_label)
        
        self.interval_spinner = Spinner(
            text=f'{app.auto_refresh_interval} min',
            values=('5 min', '15 min', '30 min', '60 min'),
            size_hint_x=0.3
        )
        self.interval_spinner.bind(text=self.change_refresh_interval)
        settings_bar.add_widget(self.interval_spinner)
        
        self.add_widget(settings_bar)
        
        # Status
        self.status_bar = Label(
            text='Connected • Ready',
            size_hint_y=0.05,
            color=GREEN,
            font_size='11sp'
        )
        self.add_widget(self.status_bar)
        
        # Channel List
        scroll = ScrollView(size_hint=(1, 0.77))
        self.channel_list = BoxLayout(orientation='vertical', size_hint_y=None, spacing='1dp')
        self.channel_list.bind(minimum_height=self.channel_list.setter('height'))
        
        scroll.add_widget(self.channel_list)
        self.add_widget(scroll)
        
        self.load_channels()
    
    def toggle_auto_refresh(self, instance, value):
        """Toggle auto-refresh"""
        self.app.set_auto_refresh(value)
        status = "Auto-refresh: ON" if value else "Auto-refresh: OFF"
        utils.show_toast(status)
    
    def toggle_wifi_only(self, instance, value):
        """Toggle WiFi only mode"""
        self.app.set_wifi_only(value)
        status = "WiFi only: ON" if value else "WiFi only: OFF"
        utils.show_toast(status)
    
    def change_refresh_interval(self, instance, value):
        """Change refresh interval"""
        interval = int(value.split()[0])
        self.app.set_refresh_interval(interval)
    
    def load_channels(self):
        """Load all channels from config"""
        self.channel_list.clear_widgets()
        channels = config_manager.load_all_channels()
        
        if not channels:
            self.channel_list.add_widget(Label(
                text='No channels added yet\nTap + to add one',
                color=FG2,
                size_hint_y=None,
                height='100dp'
            ))
            return
        
        for ch in channels:
            entry = ObserveEntry(ch)
            row = ChannelRow(
                entry,
                on_observe=self.observe_channel,
                on_edit=self.edit_channel,
                on_long_press=self.toggle_channel_enabled
            )
            self.channel_list.add_widget(row)
    
    def refresh_channels(self, instance=None):
        """Refresh the channel list"""
        self.load_channels()
        self.update_status()
    
    def observe_channel(self, observe_entry):
        """Check a channel for new videos"""
        if not observe_entry.enabled:
            utils.show_toast(f'{observe_entry.name} is disabled')
            return
        
        if self.app.wifi_only_mode:
            if not utils.is_wifi_connected():
                utils.show_toast('WiFi only mode: Not on WiFi')
                self.update_status()
                return
        
        self.status_bar.text = f'Checking {observe_entry.name}...'
        
        def _check():
            try:
                videos = downloader.check_new_videos(observe_entry.channel_data)
                observe_entry.videos = videos
                observe_entry.new_count = len(videos)
                observe_entry.last_checked = datetime.now().isoformat()
                
                config_manager.update_channel(observe_entry.channel_data)
                
                Clock.schedule_once(lambda dt: self._show_results(observe_entry), 0)
            except Exception as e:
                Clock.schedule_once(lambda dt: self._show_error(str(e)), 0)
        
        threading.Thread(target=_check, daemon=True).start()
    
    def _show_results(self, observe_entry):
        """Show observation results"""
        self.load_channels()
        
        if observe_entry.new_count > 0:
            self.app.show_videos_popup(observe_entry)
            utils.send_notification(
                f'{observe_entry.name}',
                f'{observe_entry.new_count} new video(s) found'
            )
        else:
            utils.show_toast(f'{observe_entry.name}: No new videos')
        
        self.update_status()
    
    def _show_error(self, error_msg):
        """Show error"""
        self.status_bar.text = f'✗ Error: {error_msg[:30]}'
        utils.show_toast(f'Error: {error_msg}')
    
    def update_status(self):
        """Update status bar"""
        is_wifi = utils.is_wifi_connected()
        is_mobile = utils.is_mobile_data_connected()
        
        status_parts = []
        if is_wifi:
            status_parts.append('WiFi ✓')
        elif is_mobile:
            status_parts.append('Mobile Data')
        else:
            status_parts.append('Offline')
        
        status_parts.append('Ready')
        
        self.status_bar.text = ' • '.join(status_parts)
    
    def edit_channel(self, observe_entry):
        """Open edit channel dialog"""
        self.app.show_edit_channel(observe_entry.channel_data)
    
    def toggle_channel_enabled(self, observe_entry):
        """Double tap to toggle enabled status"""
        observe_entry.channel_data['enabled'] = not observe_entry.channel_data['enabled']
        config_manager.update_channel(observe_entry.channel_data)
        self.load_channels()
    
    def show_add_channel(self, instance):
        """Show add channel dialog"""
        self.app.show_add_channel()


class VideoListScreen(BoxLayout):
    """Show videos from observation"""
    def __init__(self, app, observe_entry, **kwargs):
        super().__init__(orientation='vertical', **kwargs)
        self.app = app
        self.observe_entry = observe_entry
        
        from kivy.graphics import Color, Rectangle
        self.canvas.before.clear()
        with self.canvas.before:
            Color(*BG)
            Rectangle(size=self.size, pos=self.pos)
        
        # Header
        header = BoxLayout(orientation='horizontal', size_hint_y=0.1, padding='10dp')
        header.canvas.before.clear()
        with header.canvas.before:
            Color(*BG2)
            Rectangle(size=header.size, pos=header.pos)
        
        back_btn = Button(text='← Back', background_color=BG3, size_hint_x=0.15)
        back_btn.bind(on_press=self.go_back)
        header.add_widget(back_btn)
        
        title = Label(
            text=f'[b]{observe_entry.name}[/b]\n({len(observe_entry.videos)} videos)',
            markup=True,
            color=ACCENT,
            size_hint_x=0.85,
            font_size='16sp'
        )
        header.add_widget(title)
        
        self.add_widget(header)
        
        # Download all button
        download_bar = BoxLayout(orientation='horizontal', size_hint_y=0.08, padding='10dp', spacing='10dp')
        download_bar.canvas.before.clear()
        with download_bar.canvas.before:
            Color(*BG3)
            Rectangle(size=download_bar.size, pos=download_bar.pos)
        
        download_btn = Button(
            text='[b]⬇ Download All[/b]',
            markup=True,
            background_color=GREEN,
            size_hint_x=0.6
        )
        download_btn.bind(on_press=self.download_all)
        download_bar.add_widget(download_btn)
        
        select_label = Label(
            text='Select:',
            color=FG2,
            size_hint_x=0.2,
            font_size='11sp'
        )
        download_bar.add_widget(select_label)
        
        select_all_btn = Button(
            text='All',
            background_color=BG3,
            size_hint_x=0.1
        )
        select_all_btn.bind(on_press=self.select_all)
        download_bar.add_widget(select_all_btn)
        
        select_none_btn = Button(
            text='None',
            background_color=BG3,
            size_hint_x=0.1
        )
        select_none_btn.bind(on_press=self.select_none)
        download_bar.add_widget(select_none_btn)
        
        self.add_widget(download_bar)
        
        # Video List
        scroll = ScrollView()
        self.video_list = BoxLayout(orientation='vertical', size_hint_y=None, spacing='2dp')
        self.video_list.bind(minimum_height=self.video_list.setter('height'))
        
        self.selected_videos = set()
        
        for i, video in enumerate(observe_entry.videos):
            self.add_video_widget(video, i)
        
        scroll.add_widget(self.video_list)
        self.add_widget(scroll)
    
    def add_video_widget(self, video, index):
        """Add a video row to the list"""
        video_row = BoxLayout(orientation='horizontal', size_hint_y=None, height='110dp', padding='5dp')
        video_row.canvas.before.clear()
        with video_row.canvas.before:
            from kivy.graphics import Color, Rectangle
            Color(*BG2)
            Rectangle(size=video_row.size, pos=video_row.pos)
        
        # Checkbox
        checkbox = CheckBox(size_hint_x=0.08)
        checkbox.bind(active=lambda x, active, idx=index: self.toggle_video_selection(idx, active))
        video_row.add_widget(checkbox)
        
        # Thumbnail
        if video.get('thumbnail_url'):
            thumb = AsyncImage(
                source=video['thumbnail_url'],
                size_hint_x=0.25
            )
            video_row.add_widget(thumb)
        
        # Info
        info = BoxLayout(orientation='vertical', size_hint_x=0.6, padding='5dp', spacing='2dp')
        
        title = Label(
            text=video.get('title', 'Unknown')[:50],
            size_hint_y=0.35,
            color=FG,
            font_size='12sp',
            text_size=(self.width * 0.6, None),
            markup=True
        )
        info.add_widget(title)
        
        duration = Label(
            text=f"Duration: {video.get('duration', 'N/A')} min",
            size_hint_y=0.25,
            color=YELLOW,
            font_size='10sp'
        )
        info.add_widget(duration)
        
        upload_date = Label(
            text=f"Uploaded: {video.get('upload_date', 'N/A')}",
            size_hint_y=0.25,
            color=FG2,
            font_size='9sp'
        )
        info.add_widget(upload_date)
        
        video_row.add_widget(info)
        
        # Action button
        view_btn = Button(
            text='→',
            background_color=ACCENT,
            size_hint_x=0.07
        )
        video_row.add_widget(view_btn)
        
        self.video_list.add_widget(video_row)
    
    def toggle_video_selection(self, index, selected):
        """Toggle video selection"""
        if selected:
            self.selected_videos.add(index)
        else:
            self.selected_videos.discard(index)
    
    def select_all(self, instance):
        """Select all videos"""
        self.selected_videos = set(range(len(self.observe_entry.videos)))
        for i, child in enumerate(self.video_list.children):
            if hasattr(child, 'children'):
                for c in child.children:
                    if isinstance(c, CheckBox):
                        c.active = True
    
    def select_none(self, instance):
        """Deselect all videos"""
        self.selected_videos.clear()
        for child in self.video_list.children:
            if hasattr(child, 'children'):
                for c in child.children:
                    if isinstance(c, CheckBox):
                        c.active = False
    
    def download_all(self, instance):
        """Download selected videos"""
        if not self.selected_videos:
            utils.show_toast('Please select videos')
            return
        
        if self.app.wifi_only_mode:
            if not utils.is_wifi_connected():
                utils.show_toast('WiFi only mode: Not on WiFi')
                return
        
        selected_videos = [self.observe_entry.videos[i] for i in sorted(self.selected_videos)]
        self.app.download_videos(self.observe_entry.channel_data, selected_videos)
    
    def go_back(self, instance):
        """Return to main observe list"""
        self.app.show_observe_screen()


class EditChannelScreen(BoxLayout):
    """Edit channel configuration"""
    def __init__(self, app, channel_data=None, **kwargs):
        super().__init__(orientation='vertical', **kwargs)
        self.app = app
        self.channel_data = channel_data or {}
        
        from kivy.graphics import Color, Rectangle
        self.canvas.before.clear()
        with self.canvas.before:
            Color(*BG)
            Rectangle(size=self.size, pos=self.pos)
        
        # Header
        header = BoxLayout(orientation='horizontal', size_hint_y=0.08, padding='10dp')
        back_btn = Button(text='← Back', background_color=BG3, size_hint_x=0.15)
        back_btn.bind(on_press=self.go_back)
        header.add_widget(back_btn)
        
        title_text = 'Edit Channel' if channel_data else 'Add Channel'
        title = Label(text=f'[b]{title_text}[/b]', markup=True, color=ACCENT, font_size='18sp')
        header.add_widget(title)
        
        self.add_widget(header)
        
        # Scroll content
        scroll = ScrollView()
        form = BoxLayout(orientation='vertical', size_hint_y=None, padding='15dp', spacing='10dp')
        form.bind(minimum_height=form.setter('height'))
        
        # Channel Name
        form.add_widget(Label(text='Channel Name:', color=FG2, size_hint_y=None, height='30dp', font_size='12sp'))
        self.name_input = TextInput(
            text=channel_data.get('name', ''),
            multiline=False,
            size_hint_y=None,
            height='45dp',
            background_color=BG3,
            foreground_color=FG,
            cursor_color=ACCENT,
            padding=['10dp', '10dp']
        )
        form.add_widget(self.name_input)
        
        # Channel URL
        form.add_widget(Label(text='Channel/Playlist URL:', color=FG2, size_hint_y=None, height='30dp', font_size='12sp'))
        self.url_input = TextInput(
            text=channel_data.get('url', ''),
            multiline=False,
            size_hint_y=None,
            height='45dp',
            background_color=BG3,
            foreground_color=FG,
            cursor_color=ACCENT,
            padding=['10dp', '10dp']
        )
        form.add_widget(self.url_input)
        
        # Type
        form.add_widget(Label(text='Type:', color=FG2, size_hint_y=None, height='30dp', font_size='12sp'))
        self.type_spinner = Spinner(
            text=channel_data.get('type', 'audio'),
            values=('audio', 'video'),
            size_hint_y=None,
            height='45dp',
            background_color=BG3,
            color=FG
        )
        form.add_widget(self.type_spinner)
        
        # Format
        form.add_widget(Label(text='Format:', color=FG2, size_hint_y=None, height='30dp', font_size='12sp'))
        formats = ['m4a', 'mp3', 'opus', 'flac', 'mp4', 'mkv', 'webm']
        self.format_spinner = Spinner(
            text=channel_data.get('format', 'm4a'),
            values=formats,
            size_hint_y=None,
            height='45dp',
            background_color=BG3,
            color=FG
        )
        form.add_widget(self.format_spinner)
        
        # Audio Quality
        form.add_widget(Label(text='Audio Quality:', color=FG2, size_hint_y=None, height='30dp', font_size='12sp'))
        self.audio_quality_spinner = Spinner(
            text=channel_data.get('audio_quality', 'best'),
            values=('best', '320k', '192k', '128k'),
            size_hint_y=None,
            height='45dp',
            background_color=BG3,
            color=FG
        )
        form.add_widget(self.audio_quality_spinner)
        
        # Video Quality
        form.add_widget(Label(text='Video Quality:', color=FG2, size_hint_y=None, height='30dp', font_size='12sp'))
        self.video_quality_spinner = Spinner(
            text=channel_data.get('video_quality', 'best'),
            values=('best', '1080p', '720p', '480p'),
            size_hint_y=None,
            height='45dp',
            background_color=BG3,
            color=FG
        )
        form.add_widget(self.video_quality_spinner)
        
        # Date Filter
        form.add_widget(Label(text='Date Filter (e.g. now-7days):', color=FG2, size_hint_y=None, height='30dp', font_size='12sp'))
        self.date_input = TextInput(
            text=channel_data.get('date_filter', ''),
            multiline=False,
            size_hint_y=None,
            height='45dp',
            background_color=BG3,
            foreground_color=FG,
            cursor_color=ACCENT,
            padding=['10dp', '10dp']
        )
        form.add_widget(self.date_input)
        
        # Min Duration
        form.add_widget(Label(text='Min Duration (minutes):', color=FG2, size_hint_y=None, height='30dp', font_size='12sp'))
        self.min_duration_input = TextInput(
            text=str(channel_data.get('duration_min', 0)),
            multiline=False,
            input_filter='int',
            size_hint_y=None,
            height='45dp',
            background_color=BG3,
            foreground_color=FG,
            cursor_color=ACCENT,
            padding=['10dp', '10dp']
        )
        form.add_widget(self.min_duration_input)
        
        # Max Duration
        form.add_widget(Label(text='Max Duration (minutes):', color=FG2, size_hint_y=None, height='30dp', font_size='12sp'))
        self.max_duration_input = TextInput(
            text=str(channel_data.get('duration_max', 0)),
            multiline=False,
            input_filter='int',
            size_hint_y=None,
            height='45dp',
            background_color=BG3,
            foreground_color=FG,
            cursor_color=ACCENT,
            padding=['10dp', '10dp']
        )
        form.add_widget(self.max_duration_input)
        
        # Skip Shorts
        skip_shorts_layout = BoxLayout(size_hint_y=None, height='50dp', spacing='10dp', padding='5dp')
        skip_shorts_layout.add_widget(Label(text='Skip Shorts (<60s):', color=FG2, size_hint_x=0.7, font_size='12sp'))
        self.skip_shorts_checkbox = CheckBox(
            active=channel_data.get('skip_shorts', True),
            size_hint_x=0.3
        )
        skip_shorts_layout.add_widget(self.skip_shorts_checkbox)
        form.add_widget(skip_shorts_layout)
        
        # Keywords
        form.add_widget(Label(text='Keywords (comma separated):', color=FG2, size_hint_y=None, height='30dp', font_size='12sp'))
        keywords_str = ', '.join(channel_data.get('keywords', []))
        self.keywords_input = TextInput(
            text=keywords_str,
            multiline=False,
            size_hint_y=None,
            height='45dp',
            background_color=BG3,
            foreground_color=FG,
            cursor_color=ACCENT,
            padding=['10dp', '10dp']
        )
        form.add_widget(self.keywords_input)
        
        # Enabled toggle
        enabled_layout = BoxLayout(size_hint_y=None, height='50dp', spacing='10dp', padding='5dp')
        enabled_layout.add_widget(Label(text='Enabled:', color=FG2, size_hint_x=0.7, font_size='12sp'))
        self.enabled_checkbox = CheckBox(
            active=channel_data.get('enabled', True),
            size_hint_x=0.3
        )
        enabled_layout.add_widget(self.enabled_checkbox)
        form.add_widget(enabled_layout)
        
        # Spacer
        form.add_widget(Label(size_hint_y=None, height='10dp'))
        
        # Save Button
        save_btn = Button(
            text='[b]✓ Save[/b]',
            markup=True,
            background_color=GREEN,
            size_hint_y=None,
            height='50dp'
        )
        save_btn.bind(on_press=self.save_channel)
        form.add_widget(save_btn)
        
        # Delete Button (if editing)
        if channel_data:
            delete_btn = Button(
                text='[b]🗑 Delete[/b]',
                markup=True,
                background_color=RED,
                size_hint_y=None,
                height='50dp'
            )
            delete_btn.bind(on_press=self.delete_channel)
            form.add_widget(delete_btn)
        
        scroll.add_widget(form)
        self.add_widget(scroll)
    
    def save_channel(self, instance):
        """Save channel configuration"""
        if not self.name_input.text or not self.url_input.text:
            utils.show_toast('Please fill in all required fields')
            return
        
        channel = {
            'name': self.name_input.text,
            'url': self.url_input.text,
            'type': self.type_spinner.text,
            'format': self.format_spinner.text,
            'audio_quality': self.audio_quality_spinner.text,
            'video_quality': self.video_quality_spinner.text,
            'date_filter': self.date_input.text,
            'duration_min': int(self.min_duration_input.text or 0),
            'duration_max': int(self.max_duration_input.text or 0),
            'skip_shorts': self.skip_shorts_checkbox.active,
            'keywords': [k.strip() for k in self.keywords_input.text.split(',') if k.strip()],
            'enabled': self.enabled_checkbox.active,
            'new_count': 0,
            'last_checked': None
        }
        
        if self.channel_data:
            channel.update({
                'last_checked': self.channel_data.get('last_checked'),
                'new_count': self.channel_data.get('new_count', 0),
                'last_run': self.channel_data.get('last_run')
            })
        
        config_manager.save_channel(channel)
        utils.show_toast(f'Channel "{channel["name"]}" saved!')
        self.app.show_observe_screen()
    
    def delete_channel(self, instance):
        """Delete channel"""
        config_manager.delete_channel(self.channel_data['name'])
        utils.show_toast(f'Channel deleted!')
        self.app.show_observe_screen()
    
    def go_back(self, instance):
        """Return to main observe list"""
        self.app.show_observe_screen()


class YouTubeObserveApp(App):
    """Main application class"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.auto_refresh_enabled = False
        self.auto_refresh_interval = 30  # minutes
        self.wifi_only_mode = True
        self.auto_refresh_event = None
        self.observe_screen = None
        self.screen_manager = None
        
        config_manager.initialize()
    
    def build(self):
        self.title = 'YouTube Observe'
        Window.clearcolor = BG
        
        self.screen_manager = FloatLayout()
        self.observe_screen = ObserveListScreen(self)
        self.screen_manager.add_widget(self.observe_screen)
        
        if self.auto_refresh_enabled:
            self.start_auto_refresh()
        
        return self.screen_manager
    
    def set_auto_refresh(self, enabled):
        """Enable/disable auto-refresh"""
        self.auto_refresh_enabled = enabled
        if enabled:
            self.start_auto_refresh()
        else:
            self.stop_auto_refresh()
        
        config_manager.save_preference('auto_refresh', enabled)
    
    def set_refresh_interval(self, minutes):
        """Set refresh interval in minutes"""
        self.auto_refresh_interval = minutes
        config_manager.save_preference('refresh_interval', minutes)
        
        if self.auto_refresh_enabled:
            self.stop_auto_refresh()
            self.start_auto_refresh()
    
    def set_wifi_only(self, enabled):
        """Set WiFi only mode"""
        self.wifi_only_mode = enabled
        config_manager.save_preference('wifi_only', enabled)
    
    def start_auto_refresh(self):
        """Start auto-refresh timer"""
        if self.auto_refresh_event:
            self.auto_refresh_event.cancel()
        
        interval_seconds = self.auto_refresh_interval * 60
        self.auto_refresh_event = Clock.schedule_interval(
            self._do_auto_refresh,
            interval_seconds
        )
        
        utils.show_toast(f'Auto-refresh: Every {self.auto_refresh_interval} minutes')
    
    def stop_auto_refresh(self):
        """Stop auto-refresh timer"""
        if self.auto_refresh_event:
            self.auto_refresh_event.cancel()
            self.auto_refresh_event = None
    
    def _do_auto_refresh(self, dt):
        """Perform auto-refresh check"""
        if self.wifi_only_mode:
            if not utils.is_wifi_connected():
                return
        
        channels = config_manager.load_all_channels()
        enabled_channels = [ch for ch in channels if ch.get('enabled', True)]
        
        if not enabled_channels:
            return
        
        def _check_all():
            for ch in enabled_channels:
                try:
                    videos = downloader.check_new_videos(ch)
                    if videos:
                        ch['new_count'] = len(videos)
                        ch['last_checked'] = datetime.now().isoformat()
                        config_manager.update_channel(ch)
                        
                        utils.send_notification(
                            f'{ch["name"]}',
                            f'{len(videos)} new video(s) found'
                        )
                except Exception as e:
                    print(f"Auto-refresh error for {ch['name']}: {e}")
                
                time.sleep(2)
            
            Clock.schedule_once(lambda dt: self.observe_screen.load_channels(), 0)
        
        threading.Thread(target=_check_all, daemon=True).start()
    
    def show_observe_screen(self):
        """Switch to main observe list"""
        self.screen_manager.clear_widgets()
        self.observe_screen = ObserveListScreen(self)
        self.screen_manager.add_widget(self.observe_screen)
    
    def show_videos_popup(self, observe_entry):
        """Show videos found during observation"""
        self.screen_manager.clear_widgets()
        video_screen = VideoListScreen(self, observe_entry)
        self.screen_manager.add_widget(video_screen)
    
    def show_add_channel(self):
        """Show add channel screen"""
        self.screen_manager.clear_widgets()
        edit_screen = EditChannelScreen(self)
        self.screen_manager.add_widget(edit_screen)
    
    def show_edit_channel(self, channel_data):
        """Show edit channel screen"""
        self.screen_manager.clear_widgets()
        edit_screen = EditChannelScreen(self, channel_data)
        self.screen_manager.add_widget(edit_screen)
    
    def download_videos(self, channel, videos):
        """Download selected videos"""
        progress_popup = DownloadProgressPopup(channel['name'])
        progress_popup.open()
        
        def _download():
            try:
                video_urls = [v['url'] if v.get('url') else f"https://www.youtube.com/watch?v={v['id']}" for v in videos]
                
                downloader.download_videos(
                    channel,
                    video_urls,
                    progress_callback=lambda p: progress_popup.tracker.update(
                        p.get('current', 0),
                        p.get('total', 100),
                        p.get('file', ''),
                        p.get('speed', ''),
                        p.get('eta', '')
                    )
                )
                
                progress_popup.tracker.complete()
                
                config_manager.set_new_count(channel, 0)
                Clock.schedule_once(lambda dt: self.show_observe_screen(), 2)
                utils.show_toast(f'{len(videos)} video(s) downloaded')
            
            except Exception as e:
                utils.show_toast(f'Download error: {str(e)}')
                progress_popup.dismiss()
        
        threading.Thread(target=_download, daemon=True).start()


if __name__ == '__main__':
    YouTubeObserveApp().run()