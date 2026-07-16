import json
import os

from garmin_mcp.workout_builders import (
    build_walk_run_json,
    build_z2_walk_json,
    build_strength_json,
    build_swim_workout_json,
    _pace_to_mps,
    SWIM_STROKE_TYPES,
    SWIM_DRILL_TYPES,
)

SNAPSHOT_DIR = os.path.join(os.path.dirname(__file__), "..", "fixtures", "captured")


def test_build_walk_run_json_matches_poc_snapshot():
    """The walk/run builder must produce the exact JSON that Garmin accepted in the POC."""
    result = build_walk_run_json(
        name="POC Walk/Run 7x1m/3m Z3",
        run_seconds=60,
        walk_seconds=180,
        repeats=7,
        warmup_min=10,
        cooldown_min=8,
        hr_zone="Z3",
    )

    # Compare against the validated POC snapshot
    snapshot_path = os.path.join(SNAPSHOT_DIR, "poc_walk_run.json")
    with open(snapshot_path, "r", encoding="utf-8") as f:
        expected = json.load(f)

    assert result == expected


def test_build_z2_walk_json_structure():
    result = build_z2_walk_json(
        name="Z2 Walk 30m",
        duration_min=30,
        hr_min=110,
        hr_max=130,
    )
    assert result["workoutName"] == "Z2 Walk 30m"
    assert result["sportType"]["sportTypeKey"] == "walking"
    assert result["sportType"]["sportTypeId"] == 12
    steps = result["workoutSegments"][0]["workoutSteps"]
    assert len(steps) == 3
    assert steps[1]["zoneNumber"] == 2
    assert steps[1]["endConditionValue"] == 1800.0


def test_build_strength_json_structure():
    result = build_strength_json(
        name="Full Body A",
        exercises=[
            {"name": "Sentadillas", "sets": 3, "reps": 12, "rest_seconds": 90},
            {"name": "Flexiones", "sets": 3, "reps": 15, "rest_seconds": 60},
        ],
    )
    assert result["workoutName"] == "Full Body A"
    assert result["sportType"]["sportTypeKey"] == "strength_training"
    assert result["sportType"]["sportTypeId"] == 5
    steps = result["workoutSegments"][0]["workoutSteps"]
    # 2 exercises + 1 rest between them = 3 steps
    assert len(steps) == 3
    assert steps[0]["exerciseName"] == "Sentadillas"
    assert steps[2]["exerciseName"] == "Flexiones"


# =============================================================================
# Swim workout builder tests
# =============================================================================

def test_build_swim_workout_json_basic_structure():
    result = build_swim_workout_json(
        name="Friday Swim",
        warmup_meters=200,
        main_set=[{"distance_meters": 100, "repeats": 4, "rest_seconds": 30}],
        cooldown_meters=100,
    )
    assert result["workoutName"] == "Friday Swim"
    assert result["sportType"]["sportTypeKey"] == "swimming"
    assert result["sportType"]["sportTypeId"] == 4

    steps = result["workoutSegments"][0]["workoutSteps"]
    # warmup + RepeatGroupDTO + cooldown = 3 top-level steps
    assert len(steps) == 3
    assert steps[0]["stepType"]["stepTypeKey"] == "warmup"
    assert steps[0]["endConditionValue"] == 200.0
    assert steps[1]["type"] == "RepeatGroupDTO"
    assert steps[1]["numberOfIterations"] == 4
    assert steps[2]["stepType"]["stepTypeKey"] == "cooldown"
    assert steps[2]["endConditionValue"] == 100.0

    nested = steps[1]["workoutSteps"]
    assert nested[0]["stepType"]["stepTypeKey"] == "interval"
    assert nested[0]["endConditionValue"] == 100.0
    assert nested[1]["endCondition"]["conditionTypeKey"] == "fixed.rest"
    assert nested[1]["endConditionValue"] == 30.0


def test_build_swim_workout_json_pace_conversion():
    result = build_swim_workout_json(
        name="Pace Test",
        warmup_meters=100,
        main_set=[{
            "distance_meters": 100,
            "repeats": 3,
            "rest_seconds": 20,
            "pace_slow": "2:30",
            "pace_fast": "2:00",
        }],
        cooldown_meters=100,
    )
    interval = result["workoutSegments"][0]["workoutSteps"][1]["workoutSteps"][0]
    assert interval["targetType"] is None
    assert interval["secondaryTargetType"]["workoutTargetTypeKey"] == "pace.zone"
    # 2:30/100m → 100/150 ≈ 0.6666667 m/s
    assert abs(interval["secondaryTargetValueOne"] - _pace_to_mps("2:30")) < 1e-6
    # 2:00/100m → 100/120 ≈ 0.8333333 m/s
    assert abs(interval["secondaryTargetValueTwo"] - _pace_to_mps("2:00")) < 1e-6


def test_build_swim_workout_json_single_repeat():
    result = build_swim_workout_json(
        name="Single Effort",
        warmup_meters=100,
        main_set=[{"distance_meters": 400, "repeats": 1, "rest_seconds": 60}],
        cooldown_meters=100,
    )
    steps = result["workoutSegments"][0]["workoutSteps"]
    # warmup + single interval step (no RepeatGroupDTO) + cooldown = 3 steps
    assert len(steps) == 3
    assert steps[1]["type"] == "ExecutableStepDTO"
    assert steps[1]["stepType"]["stepTypeKey"] == "interval"
    assert steps[1]["endConditionValue"] == 400.0


def test_build_swim_workout_json_no_pace():
    result = build_swim_workout_json(
        name="Easy Swim",
        warmup_meters=200,
        main_set=[{"distance_meters": 200, "repeats": 2, "rest_seconds": 45}],
        cooldown_meters=100,
    )
    interval = result["workoutSegments"][0]["workoutSteps"][1]["workoutSteps"][0]
    assert interval["targetType"] is None
    assert "secondaryTargetType" not in interval
    assert "secondaryTargetValueOne" not in interval
    assert "secondaryTargetValueTwo" not in interval


def test_build_swim_workout_json_stroke_type():
    result = build_swim_workout_json(
        name="Backstroke Set",
        warmup_meters=100,
        main_set=[{"distance_meters": 100, "repeats": 4, "rest_seconds": 20, "stroke_type": "backstroke"}],
        cooldown_meters=100,
    )
    interval = result["workoutSegments"][0]["workoutSteps"][1]["workoutSteps"][0]
    assert "strokeType" in interval
    assert interval["strokeType"]["strokeTypeKey"] == "backstroke"
    assert interval["strokeType"]["strokeTypeId"] == SWIM_STROKE_TYPES["backstroke"]["strokeTypeId"]
    assert "drillType" not in interval


def test_build_swim_workout_json_drill_type():
    result = build_swim_workout_json(
        name="Kick Drill Set",
        warmup_meters=100,
        main_set=[{"distance_meters": 50, "repeats": 4, "rest_seconds": 15, "drill_type": "kick"}],
        cooldown_meters=100,
    )
    interval = result["workoutSegments"][0]["workoutSteps"][1]["workoutSteps"][0]
    assert "drillType" in interval
    assert interval["drillType"]["drillTypeKey"] == "kick"
    assert interval["drillType"]["drillTypeId"] == SWIM_DRILL_TYPES["kick"]["drillTypeId"]
    assert "strokeType" not in interval


def test_build_swim_workout_json_stroke_and_drill_combined():
    result = build_swim_workout_json(
        name="Pull Drill",
        warmup_meters=100,
        main_set=[{
            "distance_meters": 100,
            "repeats": 3,
            "rest_seconds": 20,
            "stroke_type": "freestyle",
            "drill_type": "pull",
        }],
        cooldown_meters=100,
    )
    interval = result["workoutSegments"][0]["workoutSteps"][1]["workoutSteps"][0]
    assert interval["strokeType"]["strokeTypeKey"] == "freestyle"
    assert interval["strokeType"]["strokeTypeId"] == SWIM_STROKE_TYPES["freestyle"]["strokeTypeId"]
    assert interval["drillType"]["drillTypeKey"] == "pull"
    assert interval["drillType"]["drillTypeId"] == SWIM_DRILL_TYPES["pull"]["drillTypeId"]


def test_build_swim_workout_json_pool_length():
    result = build_swim_workout_json(
        name="50m Pool Swim",
        warmup_meters=200,
        main_set=[{"distance_meters": 100, "repeats": 4, "rest_seconds": 30}],
        cooldown_meters=100,
        pool_length_meters=50.0,
    )
    assert result["poolLength"] == 50.0
    assert result["poolLengthUnit"]["unitKey"] == "meter"
    assert result["poolLengthUnit"]["unitId"] == 1

    result_default = build_swim_workout_json(
        name="Default Pool",
        warmup_meters=100,
        main_set=[{"distance_meters": 100, "repeats": 2, "rest_seconds": 20}],
        cooldown_meters=100,
    )
    assert result_default["poolLength"] == 25.0


def test_build_swim_workout_json_step_description():
    result = build_swim_workout_json(
        name="Drill Focus",
        warmup_meters=200,
        main_set=[{
            "distance_meters": 50,
            "repeats": 4,
            "rest_seconds": 15,
            "drill_type": "kick",
            "description": "Kick only — eyes down, tight core, ankles loose",
        }],
        cooldown_meters=100,
    )
    interval = result["workoutSegments"][0]["workoutSteps"][1]["workoutSteps"][0]
    assert interval["description"] == "Kick only — eyes down, tight core, ankles loose"


def test_build_swim_workout_json_hr_zone():
    result = build_swim_workout_json(
        name="Z2 Swim",
        warmup_meters=200,
        main_set=[{"distance_meters": 100, "repeats": 4, "rest_seconds": 30, "hr_zone": 2}],
        cooldown_meters=100,
    )
    interval = result["workoutSegments"][0]["workoutSteps"][1]["workoutSteps"][0]
    assert interval["targetType"]["workoutTargetTypeKey"] == "heart.rate.zone"
    assert interval["zoneNumber"] == 2


def test_build_swim_workout_json_invalid_stroke_type_ignored():
    result = build_swim_workout_json(
        name="Easy Swim",
        warmup_meters=100,
        main_set=[{"distance_meters": 100, "repeats": 2, "rest_seconds": 30, "stroke_type": "not_a_real_stroke"}],
        cooldown_meters=100,
    )
    interval = result["workoutSegments"][0]["workoutSteps"][1]["workoutSteps"][0]
    assert "strokeType" not in interval
