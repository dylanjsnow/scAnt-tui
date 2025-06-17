from enum import Enum
from typing import Final, Tuple

class MotorStatus(Enum):
    IDLE = "IDLE"
    MOVING = "MOVING"
    
class MotorEnergizedStatus(Enum):
    ENERGIZED = "ENERGIZED"
    UNENERGIZED = "UNENERGIZED"
    
class MotorAxis(Enum):
    FORWARD = "FORWARD"
    TILT = "TILT"
    YAW = "YAW"
    
MOTOR_AXIS_SERIALS = {
    MotorAxis.FORWARD: "1",
    MotorAxis.TILT: "2",
    MotorAxis.YAW: "3",
}
    
CURRENT_LIMIT_OPTIONS: Final[Tuple[Tuple[str, str], ...]] = (
    ("0 mA (0)", "0"),
    ("1 mA (1)", "1"),
    ("174 mA (2)", "2"),
    ("343 mA (3)", "3"),
    ("495 mA (4)", "4"),
    ("634 mA (5)", "5"),
    ("762 mA (6)", "6"),
    ("880 mA (7)", "7"),
    ("990 mA (8)", "8"),
    ("1092 mA (9)", "9"),
    ("1189 mA (10)", "10"),
    ("1281 mA (11)", "11"),
    ("1368 mA (12)", "12"),
    ("1452 mA (13)", "13"),
    ("1532 mA (14)", "14"),
    ("1611 mA (15)", "15"),
    ("1687 mA (16)", "16"),
    ("1762 mA (17)", "17"),
    ("1835 mA (18)", "18"),
    ("1909 mA (19)", "19"),
    ("1982 mA (20)", "20"),
    ("2056 mA (21)", "21"),
    ("2131 mA (22)", "22"),
    ("2207 mA (23)", "23"),
    ("2285 mA (24)", "24"),
    ("2366 mA (25)", "25"),
    ("2451 mA (26)", "26"),
    ("2540 mA (27)", "27"),
    ("2634 mA (28)", "28"),
    ("2734 mA (29)", "29"),
    ("2843 mA (30)", "30"),
    ("2962 mA (31)", "31"),
    ("3093 mA (32)", "32"),
)