class OpMixin:
    def prev_theme(self):
        """Switch to previous theme in the themes list"""
        self.switch_theme_by_offset(-1)

    def next_theme(self):
        """Switch to next theme in the themes list"""
        self.switch_theme_by_offset(+1)

    def activate_next(self):
        """Activate the managed window next to the last activated managed window"""
        self.activate_by_offset(+1)

    def activate_prev(self):
        """Activate the managed window prior to the last activated managed window"""
        self.activate_by_offset(-1)

    def swap_next(self):
        """Swap the current active managed window with its next in list"""
        self.swap_by_offset(+1)

    def swap_prev(self):
        """Swap the current active managed window with its previous in list"""
        self.swap_by_offset(-1)

    def prev_monitor(self):
        """Switch to previous monitor"""
        self.switch_monitor_by_offset(-1)

    def next_monitor(self):
        """Switch to next monitor"""
        self.switch_monitor_by_offset(+1)

    def move_to_prev_monitor(self):
        """Move active window to previous monitor"""
        self.move_to_monitor_by_offset(-1)

    def move_to_next_monitor(self):
        """Move active window to next monitor"""
        self.move_to_monitor_by_offset(+1)
