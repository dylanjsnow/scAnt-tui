from textual.widgets import ProgressBar
import logging

# Create logger for this module
logger = logging.getLogger(__name__)

class ProgressDisplay(ProgressBar):
    """A widget to display division and position progress using a progress bar"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(
            total=100,  # Use percentage for total
            show_bar=True,
            show_percentage=True,
            show_eta=False,  # Changed from True to False
            name="progress_display",
            id="progress_display"
        )
        self.total_divisions = 0
        self.current_division = 0
        self.current_position = 0
        self.target_position = 0
        self.start_position = 0  # Track start position of current movement
        self.position_tolerance = 0.05
        
        # Initialize with some progress to make it visible
        self.update(progress=1)  # Set initial progress to 1% to make bar visible
        logger.debug("ProgressDisplay initialized")

    def update_progress(self, current_division: int, total_divisions: int, 
                       current_pos: float, target_pos: float, wait_time: float = 2.0) -> None:
        """Update progress based on both division and position progress"""
        try:
            # Convert string values to numeric if needed
            if isinstance(total_divisions, str) and total_divisions.isdigit():
                total_divisions = int(total_divisions)
            if isinstance(current_pos, str) and current_pos.replace('-', '').replace('.', '').isdigit():
                current_pos = float(current_pos)
            if isinstance(target_pos, str) and target_pos.replace('-', '').replace('.', '').isdigit():
                target_pos = float(target_pos)
            
            self.total_divisions = max(1, total_divisions)
            self.current_division = current_division
            self.current_position = float(current_pos)
            self.target_position = float(target_pos)
            
            # Base progress from completed divisions
            division_progress = (self.current_division / self.total_divisions) * 100
            
            # Calculate progress within current division
            if self.current_division < self.total_divisions:
                # Calculate position progress as percentage of total movement
                total_movement = abs(self.target_position - self.start_position)
                if total_movement > 0:
                    remaining_movement = abs(self.target_position - self.current_position)
                    position_progress = ((total_movement - remaining_movement) / total_movement)
                else:
                    position_progress = 1.0
                
                # Each division contributes an equal percentage to total progress
                division_contribution = 100.0 / self.total_divisions
                current_division_progress = position_progress * division_contribution
                
                # Combine base progress with current division progress
                total_progress = division_progress + current_division_progress
            else:
                total_progress = 100.0
            
            logger.debug(f"Progress: {total_progress:.1f}% (Division {self.current_division}/{self.total_divisions}, "
                      f"Position: {self.current_position:.1f}/{self.target_position:.1f})")
            
            # Ensure progress is at least 1% to make the bar visible
            self.update(progress=max(1, min(100, total_progress)))
            
        except Exception as e:
            logger.error(f"Error updating progress: {e}")

    def start_new_movement(self, start_pos: float, target_pos: float) -> None:
        """Called when starting movement to a new position"""
        try:
            self.start_position = float(start_pos)
            self.target_position = float(target_pos)
            logger.debug(f"Starting new movement from {start_pos} to {target_pos}")
        except Exception as e:
            logger.error(f"Error starting new movement: {e}")

    def update_total_divisions(self, divisions: str) -> None:
        """Update the total number of divisions"""
        try:
            if divisions:
                # Handle string values
                if isinstance(divisions, str):
                    if divisions.isdigit():
                        self.total_divisions = int(divisions)
                    else:
                        self.total_divisions = 1
                else:
                    self.total_divisions = int(divisions)
            else:
                self.total_divisions = 1
            
            logger.debug(f"Updated total divisions to {self.total_divisions}")
            
            # Update with minimal progress to make bar visible
            self.update(progress=1)
            
        except (ValueError, TypeError) as e:
            logger.error(f"Error updating total divisions: {e}")
            self.total_divisions = 1
            self.update(progress=1)

    def reset(self) -> None:
        """Reset the progress tracking"""
        try:
            self.current_division = 0
            self.start_position = 0
            # Set to 1% instead of 0 to keep bar visible
            self.update(progress=1)
            logger.debug("Progress bar reset")
        except Exception as e:
            logger.error(f"Error resetting progress bar: {e}")
