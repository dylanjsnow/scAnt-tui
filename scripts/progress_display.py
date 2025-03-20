from textual.widgets import ProgressBar
import logging

# Create logger for this module
logger = logging.getLogger(__name__)

class ProgressDisplay(ProgressBar):
    """A simplified progress display for stepper motor position"""
    
    def __init__(self, id: str = None):
        """Initialize the progress display"""
        super().__init__(id=id, show_eta=False)  # Don't show ETA since we're tracking position
        self.min_position = 0
        self.max_position = 0
        logger.debug(f"Initialized ProgressDisplay {id}")

    def set_range(self, min_position: float, max_position: float) -> None:
        """Set the position range for the progress bar"""
        try:
            self.min_position = float(min_position)
            self.max_position = float(max_position)
            # Set the total steps for the progress bar
            self.total = abs(self.max_position - self.min_position)
            logger.debug(f"{self.id}: Set range min={self.min_position}, max={self.max_position}, total={self.total}")
        except ValueError as e:
            logger.error(f"{self.id}: Error setting range: {e}")

    def update_progress(self, current_position: float) -> None:
        """Update the progress bar based on current position"""
        try:
            if self.max_position == self.min_position:
                logger.debug(f"{self.id}: Min and max positions are equal, setting progress to 0")
                self.update(progress=0)
                return

            # Calculate absolute progress from min position
            position = float(current_position)
            progress = abs(position - self.min_position)
            
            # Update progress bar
            self.update(progress=progress)
            
            logger.debug(f"{self.id}: Updated progress - pos={position}, progress={progress}")
            
        except (ValueError, ZeroDivisionError) as e:
            logger.error(f"{self.id}: Error updating progress: {e}")
            self.update(progress=0)

    def reset(self) -> None:
        """Reset the progress tracking"""
        try:
            self.update(progress=0, total=None)  # Reset to indeterminate state
            logger.debug(f"{self.id}: Progress bar reset")
        except Exception as e:
            logger.error(f"Error resetting progress bar: {e}")
