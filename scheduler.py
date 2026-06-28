import datetime
try:
    import database
except ImportError:
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    import database

def time_to_minutes(time_str: str) -> int:
    """Converts 'HH:MM' time string to minutes since midnight."""
    h, m = map(int, time_str.split(":"))
    return h * 60 + m

def minutes_to_time(minutes: int) -> str:
    """Converts minutes since midnight to 'HH:MM' time string."""
    h = minutes // 60
    m = minutes % 60
    return f"{h:02d}:{m:02d}"

def get_day_itinerary(day_name: str = None) -> str:
    """
    Schedules today's flexible tasks around hard constraints.
    Returns a structured textual itinerary.
    """
    if not day_name:
        day_name = datetime.datetime.now().strftime("%A")
        
    # Get database records
    hard_constraints = database.get_hard_constraints(day_name)
    flexible_tasks = database.get_pending_flexible_tasks()
    
    # Initialize scheduling window (08:00 to 22:00)
    day_start = time_to_minutes("08:00")
    day_end = time_to_minutes("22:00")
    
    # Free slots tracking: starts as one full slot [start_min, end_min]
    free_slots = [[day_start, day_end]]
    
    # Schedule timeline holds all finalized scheduled items:
    # {"start": int, "end": int, "type": "hard"|"flexible", "title": str}
    itinerary_items = []
    
    # Process Hard Constraints first
    for hc in hard_constraints:
        hc_start = time_to_minutes(hc["start_time"])
        hc_end = time_to_minutes(hc["end_time"])
        
        itinerary_items.append({
            "start": hc_start,
            "end": hc_end,
            "type": "hard",
            "title": hc["title"]
        })
        
        # Deduct hard constraint times from free slots
        new_free_slots = []
        for slot in free_slots:
            s_start, s_end = slot
            # Check overlap
            if hc_start < s_end and hc_end > s_start:
                # Add pre-constraint slot if valid
                if hc_start > s_start:
                    new_free_slots.append([s_start, hc_start])
                # Add post-constraint slot if valid
                if hc_end < s_end:
                    new_free_slots.append([hc_end, s_end])
            else:
                new_free_slots.append(slot)
        free_slots = new_free_slots
        
    # Process Flexible Tasks greedily by priority score
    unscheduled_tasks = []
    for task in flexible_tasks:
        duration = task["duration_minutes"]
        scheduled = False
        
        # Look for the first free slot that fits this task
        # Free slots are sorted by start time
        free_slots.sort(key=lambda x: x[0])
        
        for i, slot in enumerate(free_slots):
            s_start, s_end = slot
            if (s_end - s_start) >= duration:
                # Schedule task at the beginning of this slot
                task_start = s_start
                task_end = s_start + duration
                
                itinerary_items.append({
                    "start": task_start,
                    "end": task_end,
                    "type": "flexible",
                    "title": task["title"]
                })
                
                # Shrink/replace the free slot
                if task_end < s_end:
                    free_slots[i] = [task_end, s_end]
                else:
                    free_slots.pop(i)
                    
                scheduled = True
                break
                
        if not scheduled:
            unscheduled_tasks.append(task)
            
    # Sort finalized itinerary by start time
    itinerary_items.sort(key=lambda x: x["start"])
    
    # Format the itinerary string
    lines = [f"📅 Itinerary for {day_name}:"]
    if not itinerary_items:
        lines.append("   (No events scheduled today.)")
    else:
        for item in itinerary_items:
            time_range = f"{minutes_to_time(item['start'])} - {minutes_to_time(item['end'])}"
            prefix = "[FIXED]" if item["type"] == "hard" else "[TASK]"
            lines.append(f"  🕒 {time_range} : {prefix} {item['title']}")
            
    if unscheduled_tasks:
        lines.append("\n⚠️ Unscheduled / Backlog Tasks:")
        for ut in unscheduled_tasks:
            lines.append(f"  - {ut['title']} ({ut['duration_minutes']} mins, Priority {ut['priority_score']})")
            
    return "\n".join(lines)

if __name__ == "__main__":
    # Test for Wednesday (has one hard constraint, three flexible tasks)
    print(get_day_itinerary("Wednesday"))
