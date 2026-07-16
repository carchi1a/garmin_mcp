"""
High-level workout builders for Garmin Connect MCP Server.

These tools construct the internal Garmin Connect JSON internally and delegate
to the existing upload_workout / schedule_workout endpoints.
"""
import json
from typing import Any, Dict, List, Optional

# The garmin_client will be set by the main file
garmin_client = None


def configure(client):
    """Configure the module with the Garmin client instance"""
    global garmin_client
    garmin_client = client


# =============================================================================
# JSON BUILDERS
# =============================================================================

HR_ZONE_MAP = {
    "Z1": 1,
    "Z2": 2,
    "Z3": 3,
    "Z4": 4,
    "Z5": 5,
}

# strokeTypeId values are inferred from the Garmin FIT SDK and UI observation.
# ⚠️ Validate against a live API response - workout builder IDs may differ from FIT SDK.
SWIM_STROKE_TYPES = {
    "freestyle":    {"strokeTypeId": 0, "strokeTypeKey": "freestyle",    "displayOrder": 1},
    "backstroke":   {"strokeTypeId": 1, "strokeTypeKey": "backstroke",   "displayOrder": 2},
    "breaststroke": {"strokeTypeId": 2, "strokeTypeKey": "breaststroke", "displayOrder": 3},
    "butterfly":    {"strokeTypeId": 3, "strokeTypeKey": "butterfly",    "displayOrder": 4},
    "choice":       {"strokeTypeId": 4, "strokeTypeKey": "choice",       "displayOrder": 5},
    "im":           {"strokeTypeId": 5, "strokeTypeKey": "im",           "displayOrder": 6},
    "im_by_round":  {"strokeTypeId": 6, "strokeTypeKey": "im_by_round",  "displayOrder": 7},
    "rimo":         {"strokeTypeId": 7, "strokeTypeKey": "rimo",         "displayOrder": 8},
    "mixed":        {"strokeTypeId": 8, "strokeTypeKey": "mixed",        "displayOrder": 9},
}

# drillTypeId values are not documented in any public source.
# ⚠️ Validate against a live API response before relying on these IDs.
SWIM_DRILL_TYPES = {
    "kick":  {"drillTypeId": 1, "drillTypeKey": "kick",  "displayOrder": 1},
    "pull":  {"drillTypeId": 2, "drillTypeKey": "pull",  "displayOrder": 2},
    "drill": {"drillTypeId": 3, "drillTypeKey": "drill", "displayOrder": 3},
}


def _zone_number(zone: str) -> int:
    """Resolve a human-friendly zone string like 'Z3' to Garmin's zoneNumber."""
    zone_upper = zone.strip().upper()
    if zone_upper in HR_ZONE_MAP:
        return HR_ZONE_MAP[zone_upper]
    # Fallback: if user passed a digit directly
    try:
        z = int(zone_upper)
        if 1 <= z <= 5:
            return z
    except ValueError:
        pass
    raise ValueError(f"Invalid hr_zone '{zone}'. Use Z1-Z5 or 1-5.")


def _pace_to_mps(pace_str: str) -> float:
    """Convert 'M:SS' per 100m string to m/s (e.g. '2:30' → 0.6666667)."""
    parts = pace_str.strip().split(":")
    total_seconds = int(parts[0]) * 60 + int(parts[1])
    return round(100.0 / total_seconds, 7)


def _swim_rest_step(step_order: int, rest_seconds: int, description: str = "") -> dict:
    """Build a fixed-duration swim rest step (stepTypeId 5 / fixed.rest)."""
    return {
        "type": "ExecutableStepDTO",
        "stepOrder": step_order,
        "stepType": {"stepTypeId": 5, "stepTypeKey": "rest"},
        "description": description or f"Rest {rest_seconds}s",
        "endCondition": {"conditionTypeId": 8, "conditionTypeKey": "fixed.rest"},
        "endConditionValue": float(rest_seconds),
        "targetType": None,
    }


def build_walk_run_json(
    name: str,
    run_seconds: int,
    walk_seconds: int,
    repeats: int,
    warmup_min: int,
    cooldown_min: int,
    hr_zone: str = "Z3",
) -> dict:
    """Build the Garmin Connect JSON for a walk/run interval workout.

    Parameters match create_walk_run_workout exactly.
    """
    zone = _zone_number(hr_zone)
    return {
        "workoutName": name,
        "description": (
            f"{warmup_min}m warmup + {repeats}x({run_seconds}s run / {walk_seconds}s walk) Z{zone} + "
            f"{cooldown_min}m cooldown"
        ),
        "sportType": {"sportTypeId": 1, "sportTypeKey": "running"},
        "workoutSegments": [{
            "segmentOrder": 1,
            "sportType": {"sportTypeId": 1, "sportTypeKey": "running"},
            "workoutSteps": [
                {
                    "type": "ExecutableStepDTO",
                    "stepOrder": 1,
                    "stepType": {"stepTypeId": 1, "stepTypeKey": "warmup"},
                    "description": f"Warmup {warmup_min} min",
                    "endCondition": {"conditionTypeId": 2, "conditionTypeKey": "time"},
                    "endConditionValue": float(warmup_min * 60),
                    "targetType": {"workoutTargetTypeId": 1, "workoutTargetTypeKey": "no.target"},
                },
                {
                    "type": "RepeatGroupDTO",
                    "stepOrder": 2,
                    "numberOfIterations": repeats,
                    "workoutSteps": [
                        {
                            "type": "ExecutableStepDTO",
                            "stepOrder": 1,
                            "stepType": {"stepTypeId": 3, "stepTypeKey": "interval"},
                            "description": f"Run {run_seconds}s Z{zone}",
                            "endCondition": {"conditionTypeId": 2, "conditionTypeKey": "time"},
                            "endConditionValue": float(run_seconds),
                            "targetType": {"workoutTargetTypeId": 4, "workoutTargetTypeKey": "heart.rate.zone"},
                            "zoneNumber": zone,
                        },
                        {
                            "type": "ExecutableStepDTO",
                            "stepOrder": 2,
                            "stepType": {"stepTypeId": 4, "stepTypeKey": "recovery"},
                            "description": f"Walk {walk_seconds}s Z{zone}",
                            "endCondition": {"conditionTypeId": 2, "conditionTypeKey": "time"},
                            "endConditionValue": float(walk_seconds),
                            "targetType": {"workoutTargetTypeId": 4, "workoutTargetTypeKey": "heart.rate.zone"},
                            "zoneNumber": zone,
                        },
                    ],
                },
                {
                    "type": "ExecutableStepDTO",
                    "stepOrder": 3,
                    "stepType": {"stepTypeId": 2, "stepTypeKey": "cooldown"},
                    "description": f"Cooldown {cooldown_min} min",
                    "endCondition": {"conditionTypeId": 2, "conditionTypeKey": "time"},
                    "endConditionValue": float(cooldown_min * 60),
                    "targetType": {"workoutTargetTypeId": 1, "workoutTargetTypeKey": "no.target"},
                },
            ],
        }],
    }


def build_z2_walk_json(
    name: str,
    duration_min: int,
    hr_min: int,
    hr_max: int,
) -> dict:
    """Build the Garmin Connect JSON for a steady Z2 walking workout with absolute HR range."""
    return {
        "workoutName": name,
        "description": f"Walk {duration_min} min at Z2 ({hr_min}-{hr_max} bpm)",
        "sportType": {"sportTypeId": 12, "sportTypeKey": "walking"},
        "workoutSegments": [{
            "segmentOrder": 1,
            "sportType": {"sportTypeId": 12, "sportTypeKey": "walking"},
            "workoutSteps": [
                {
                    "type": "ExecutableStepDTO",
                    "stepOrder": 1,
                    "stepType": {"stepTypeId": 1, "stepTypeKey": "warmup"},
                    "description": "Warmup 5 min",
                    "endCondition": {"conditionTypeId": 2, "conditionTypeKey": "time"},
                    "endConditionValue": 300.0,
                    "targetType": {"workoutTargetTypeId": 1, "workoutTargetTypeKey": "no.target"},
                },
                {
                    "type": "ExecutableStepDTO",
                    "stepOrder": 2,
                    "stepType": {"stepTypeId": 3, "stepTypeKey": "interval"},
                    "description": f"Walk {duration_min} min Z2",
                    "endCondition": {"conditionTypeId": 2, "conditionTypeKey": "time"},
                    "endConditionValue": float(duration_min * 60),
                    "targetType": {"workoutTargetTypeId": 4, "workoutTargetTypeKey": "heart.rate.zone"},
                    "zoneNumber": 2,
                },
                {
                    "type": "ExecutableStepDTO",
                    "stepOrder": 3,
                    "stepType": {"stepTypeId": 2, "stepTypeKey": "cooldown"},
                    "description": "Cooldown 5 min",
                    "endCondition": {"conditionTypeId": 2, "conditionTypeKey": "time"},
                    "endConditionValue": 300.0,
                    "targetType": {"workoutTargetTypeId": 1, "workoutTargetTypeKey": "no.target"},
                },
            ],
        }],
    }


# Simplified internal exercise catalog (English → Garmin exerciseName key or fallback)
# Garmin strength workouts use exerciseName as a free-text label when the exercise
# is not in their catalog. For structured strength, we use "Other" (generic) and
# put the user name in description / exerciseName.

def build_strength_json(
    name: str,
    exercises: List[Dict[str, Any]],
) -> dict:
    """Build the Garmin Connect JSON for a strength workout.

    Each exercise maps to a generic step; if the name is not recognised in the
    Garmin catalog we use 'Other' and put the original name in exerciseName.
    """
    steps: List[dict] = []
    step_order = 1

    for ex in exercises:
        ex_name = ex.get("name", "Exercise")
        sets = int(ex.get("sets", 1))
        reps = int(ex.get("reps", 1))
        rest_seconds = int(ex.get("rest_seconds", 60))

        # Work step
        steps.append({
            "type": "ExecutableStepDTO",
            "stepOrder": step_order,
            "stepType": {"stepTypeId": 3, "stepTypeKey": "interval"},
            "description": f"{ex_name}: {sets} sets x {reps} reps",
            "endCondition": {"conditionTypeId": 2, "conditionTypeKey": "time"},
            "endConditionValue": float(sets * 45),  # rough estimate: 45s per set
            "targetType": {"workoutTargetTypeId": 1, "workoutTargetTypeKey": "no.target"},
            "exerciseName": ex_name,
        })
        step_order += 1

        # Rest step (skip after last exercise)
        if rest_seconds > 0 and ex != exercises[-1]:
            steps.append({
                "type": "ExecutableStepDTO",
                "stepOrder": step_order,
                "stepType": {"stepTypeId": 4, "stepTypeKey": "recovery"},
                "description": f"Rest {rest_seconds}s",
                "endCondition": {"conditionTypeId": 2, "conditionTypeKey": "time"},
                "endConditionValue": float(rest_seconds),
                "targetType": {"workoutTargetTypeId": 1, "workoutTargetTypeKey": "no.target"},
            })
            step_order += 1

    return {
        "workoutName": name,
        "description": f"Strength: {len(exercises)} exercises",
        "sportType": {"sportTypeId": 5, "sportTypeKey": "strength_training"},
        "workoutSegments": [{
            "segmentOrder": 1,
            "sportType": {"sportTypeId": 5, "sportTypeKey": "strength_training"},
            "workoutSteps": steps,
        }],
    }


def build_swim_workout_json(
    name: str,
    warmup_meters: int,
    main_set: List[Dict[str, Any]],
    cooldown_meters: int,
    pool_length_meters: float = 25.0,
    description: str = "",
) -> dict:
    """Build the Garmin Connect JSON for a swim (lap swimming) workout.

    Each entry in main_set may have:
        distance_meters (int): distance per interval; omit for a standalone rest step
        repeats (int): number of repetitions (>1 wraps in RepeatGroupDTO)
        rest_seconds (int): rest after each rep using fixed.rest (0 = no rest step);
            with repeats > 1 the rest goes inside the repeat group, with repeats == 1
            it follows the interval as its own step
        pace_slow (str, optional): slowest target pace as 'M:SS' per 100m
        pace_fast (str, optional): fastest target pace as 'M:SS' per 100m
        hr_zone (int, optional): heart-rate zone target 1-5 (mutually exclusive with pace)
        stroke_type (str, optional): one of freestyle|backstroke|breaststroke|butterfly|
            choice|im|im_by_round|rimo|mixed
        drill_type (str, optional): one of kick|pull|drill (independent of stroke_type)

    An entry with rest_seconds but no distance_meters becomes a standalone rest
    step (e.g. {"rest_seconds": 60} between two main-set blocks).
    """
    swim_sport = {"sportTypeId": 4, "sportTypeKey": "swimming"}
    steps: List[dict] = []
    step_order = 1

    steps.append({
        "type": "ExecutableStepDTO",
        "stepOrder": step_order,
        "stepType": {"stepTypeId": 1, "stepTypeKey": "warmup"},
        "description": f"Warmup {warmup_meters}m",
        "endCondition": {"conditionTypeId": 3, "conditionTypeKey": "distance"},
        "endConditionValue": float(warmup_meters),
        "targetType": None,
    })
    step_order += 1

    for entry in main_set:
        repeats = int(entry.get("repeats", 1))
        rest_secs = int(entry.get("rest_seconds", 0))

        # Standalone rest step: no distance given (or distance 0)
        if not entry.get("distance_meters"):
            if rest_secs <= 0:
                raise ValueError(
                    "main_set entry needs distance_meters, rest_seconds, or both"
                )
            steps.append(
                _swim_rest_step(step_order, rest_secs, entry.get("description", ""))
            )
            step_order += 1
            continue

        dist = int(entry["distance_meters"])
        pace_slow = entry.get("pace_slow")
        pace_fast = entry.get("pace_fast")
        step_desc = entry.get("description") or f"{dist}m"

        interval_step: dict = {
            "type": "ExecutableStepDTO",
            "stepOrder": 1 if repeats > 1 else step_order,
            "stepType": {"stepTypeId": 3, "stepTypeKey": "interval"},
            "description": step_desc,
            "endCondition": {"conditionTypeId": 3, "conditionTypeKey": "distance"},
            "endConditionValue": float(dist),
            "targetType": None,
        }
        if pace_slow and pace_fast:
            interval_step["secondaryTargetType"] = {
                "workoutTargetTypeId": 6,
                "workoutTargetTypeKey": "pace.zone",
            }
            interval_step["secondaryTargetValueOne"] = _pace_to_mps(pace_slow)
            interval_step["secondaryTargetValueTwo"] = _pace_to_mps(pace_fast)

        hr_zone = entry.get("hr_zone")
        if hr_zone is not None:
            interval_step["targetType"] = {
                "workoutTargetTypeId": 4,
                "workoutTargetTypeKey": "heart.rate.zone",
            }
            interval_step["zoneNumber"] = int(hr_zone)

        stroke_key = entry.get("stroke_type", "").lower()
        drill_key = entry.get("drill_type", "").lower()
        if stroke_key in SWIM_STROKE_TYPES:
            interval_step["strokeType"] = SWIM_STROKE_TYPES[stroke_key]
        if drill_key in SWIM_DRILL_TYPES:
            interval_step["drillType"] = SWIM_DRILL_TYPES[drill_key]

        if repeats > 1:
            nested: List[dict] = [interval_step]
            if rest_secs > 0:
                nested.append(_swim_rest_step(2, rest_secs))
            steps.append({
                "type": "RepeatGroupDTO",
                "stepOrder": step_order,
                "numberOfIterations": repeats,
                "workoutSteps": nested,
            })
            step_order += 1
        else:
            steps.append(interval_step)
            step_order += 1
            if rest_secs > 0:
                steps.append(_swim_rest_step(step_order, rest_secs))
                step_order += 1

    steps.append({
        "type": "ExecutableStepDTO",
        "stepOrder": step_order,
        "stepType": {"stepTypeId": 2, "stepTypeKey": "cooldown"},
        "description": f"Cooldown {cooldown_meters}m",
        "endCondition": {"conditionTypeId": 3, "conditionTypeKey": "distance"},
        "endConditionValue": float(cooldown_meters),
        "targetType": None,
    })

    set_summary = ", ".join(
        f"{e.get('repeats', 1)}x{e['distance_meters']}m"
        if e.get("distance_meters")
        else f"{e.get('rest_seconds', 0)}s rest"
        for e in main_set
    )
    auto_desc = description or (
        f"{warmup_meters}m warmup + {set_summary} + {cooldown_meters}m cooldown"
    )

    return {
        "workoutName": name,
        "description": auto_desc,
        "sportType": swim_sport,
        "poolLength": float(pool_length_meters),
        "poolLengthUnit": {"unitId": 1, "unitKey": "meter", "factor": 100.0},
        "workoutSegments": [{
            "segmentOrder": 1,
            "sportType": swim_sport,
            "workoutSteps": steps,
        }],
    }


# =============================================================================
# MCP TOOLS
# =============================================================================

def register_tools(app):
    """Register all high-level workout builder tools with the MCP server app"""

    @app.tool()
    async def create_walk_run_workout(
        name: str,
        run_seconds: int,
        walk_seconds: int,
        repeats: int,
        warmup_min: int,
        cooldown_min: int,
        hr_zone: str = "Z3",
    ) -> str:
        """Create a walk/run interval workout and upload it to Garmin Connect.

        Builds the internal Garmin JSON automatically and returns the new workout ID.

        Args:
            name: Workout name (e.g. "W3 Mié 2:2")
            run_seconds: Duration of each run interval in seconds
            walk_seconds: Duration of each walk/recovery interval in seconds
            repeats: Number of run/walk repetitions
            warmup_min: Warmup duration in minutes
            cooldown_min: Cooldown duration in minutes
            hr_zone: Target heart-rate zone (Z1-Z5, default Z3)
        """
        try:
            workout_json = build_walk_run_json(
                name=name,
                run_seconds=run_seconds,
                walk_seconds=walk_seconds,
                repeats=repeats,
                warmup_min=warmup_min,
                cooldown_min=cooldown_min,
                hr_zone=hr_zone,
            )
            result = garmin_client.upload_workout(workout_json)

            if isinstance(result, dict):
                curated = {
                    "status": "success",
                    "workout_id": result.get("workoutId"),
                    "name": result.get("workoutName"),
                    "message": "Workout uploaded successfully",
                }
                curated = {k: v for k, v in curated.items() if v is not None}
                return json.dumps(curated, indent=2)
            return json.dumps(result, indent=2)
        except Exception as e:
            return f"Error creating walk/run workout: {str(e)}"

    @app.tool()
    async def create_z2_walk_workout(
        name: str,
        duration_min: int,
        hr_min: int,
        hr_max: int,
    ) -> str:
        """Create a steady Z2 walking workout and upload it to Garmin Connect.

        Args:
            name: Workout name
            duration_min: Main walking block duration in minutes
            hr_min: Minimum heart rate in bpm (used for description; target is Z2)
            hr_max: Maximum heart rate in bpm (used for description; target is Z2)
        """
        try:
            workout_json = build_z2_walk_json(
                name=name,
                duration_min=duration_min,
                hr_min=hr_min,
                hr_max=hr_max,
            )
            result = garmin_client.upload_workout(workout_json)

            if isinstance(result, dict):
                curated = {
                    "status": "success",
                    "workout_id": result.get("workoutId"),
                    "name": result.get("workoutName"),
                    "message": "Workout uploaded successfully",
                }
                curated = {k: v for k, v in curated.items() if v is not None}
                return json.dumps(curated, indent=2)
            return json.dumps(result, indent=2)
        except Exception as e:
            return f"Error creating Z2 walk workout: {str(e)}"

    @app.tool()
    async def create_strength_workout(
        name: str,
        exercises: List[Dict[str, Any]],
    ) -> str:
        """Create a strength workout and upload it to Garmin Connect.

        Each exercise is mapped to a generic step; unsupported names fallback to
        "Other" with the original name stored in exerciseName.

        Args:
            name: Workout name
            exercises: List of dicts with keys: name, sets, reps, rest_seconds
        """
        try:
            workout_json = build_strength_json(name=name, exercises=exercises)
            result = garmin_client.upload_workout(workout_json)

            if isinstance(result, dict):
                curated = {
                    "status": "success",
                    "workout_id": result.get("workoutId"),
                    "name": result.get("workoutName"),
                    "message": "Workout uploaded successfully",
                }
                curated = {k: v for k, v in curated.items() if v is not None}
                return json.dumps(curated, indent=2)
            return json.dumps(result, indent=2)
        except Exception as e:
            return f"Error creating strength workout: {str(e)}"

    @app.tool()
    async def create_swim_workout(
        name: str,
        main_set: List[Dict[str, Any]],
        pool_length_meters: float = 25.0,
        warmup_meters: int = 200,
        cooldown_meters: int = 100,
        description: str = "",
    ) -> str:
        """PREFERRED tool for creating pool (lap) swimming workouts on Garmin Connect.

        Use this instead of upload_workout for any swim workout. It automatically
        handles pool length, stroke types, drill types, HR zone targets, distance-
        based steps, and Garmin's swim-specific JSON format.

        Structure: fixed warmup → main_set entries (in order) → fixed cooldown.
        All distances are in METRES. Do NOT pass pool lengths, step counts, or
        JSON strings - use the typed parameters below.

        Args:
            name: Workout name.
            main_set: List of dicts, each describing one block of the main set.
                Swim block entry keys:
                  distance_meters (int) - metres per repetition
                  repeats         (int) - number of reps; >1 creates a repeat group
                  rest_seconds    (int) - fixed rest after each rep (0 = no rest step);
                                          with repeats == 1 the rest follows the
                                          interval as its own step
                Standalone rest entry: omit distance_meters and set rest_seconds
                only, e.g. {"rest_seconds": 60} adds a rest step between blocks.
                Optional keys per entry:
                  description (str) - step note shown in Garmin Connect, e.g.
                                      drill focus cues or technique reminders
                  stroke_type (str) - one of: freestyle, backstroke, breaststroke,
                                      butterfly, choice, im, im_by_round, rimo, mixed
                  drill_type  (str) - one of: kick, pull, drill
                  hr_zone     (int) - heart-rate zone 1-5 (do not combine with pace)
                  pace_slow   (str) - slowest target pace as "M:SS" per 100 m
                  pace_fast   (str) - fastest target pace as "M:SS" per 100 m
            pool_length_meters: Length of the pool in metres (default 25). Common
                                values: 25 (short course), 50 (long course), 22.86
                                (25 yards). Used by the watch to measure distance per lap.
            warmup_meters:   Warmup distance in metres (default 200).
            cooldown_meters: Cooldown distance in metres (default 100).
            description:     Optional free-text description (auto-generated if blank).
        """
        try:
            workout_json = build_swim_workout_json(
                name=name,
                warmup_meters=warmup_meters,
                main_set=main_set,
                cooldown_meters=cooldown_meters,
                pool_length_meters=pool_length_meters,
                description=description,
            )
            result = garmin_client.upload_workout(workout_json)

            if isinstance(result, dict):
                curated = {
                    "status": "success",
                    "workout_id": result.get("workoutId"),
                    "name": result.get("workoutName"),
                    "message": "Workout uploaded successfully",
                }
                curated = {k: v for k, v in curated.items() if v is not None}
                return json.dumps(curated, indent=2)
            return json.dumps(result, indent=2)
        except Exception as e:
            return f"Error creating swim workout: {str(e)}"

    @app.tool()
    async def schedule_week(week: List[Dict[str, Any]]) -> str:
        """Schedule a list of workouts for the week in a single call.

        Args:
            week: List of dicts with keys: date (YYYY-MM-DD), workout_id (int)
        """
        try:
            results = []
            for item in week:
                calendar_date = item["date"]
                workout_id = int(item["workout_id"])
                url = f"workout-service/schedule/{workout_id}"
                response = garmin_client.garth.post(
                    "connectapi", url, json={"date": calendar_date}
                )
                if response.status_code == 200:
                    results.append({
                        "date": calendar_date,
                        "workout_id": workout_id,
                        "status": "scheduled",
                    })
                else:
                    results.append({
                        "date": calendar_date,
                        "workout_id": workout_id,
                        "status": "failed",
                        "http_status": response.status_code,
                    })
            return json.dumps({
                "status": "complete",
                "scheduled": results,
            }, indent=2)
        except Exception as e:
            return f"Error scheduling week: {str(e)}"

    return app
