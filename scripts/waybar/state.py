import inspect
import os

def read_state(statefile=None):
    """
    Read state from file, default to 0 if missing or invalid.
    """
    if statefile.exists():
        try:
            return int(statefile.read_text().strip())
        except:
            write_state(statefile=statefile, state_number=0)
            return 0
    write_state(statefile=statefile, state_number=0)
    return 0

def write_state(statefile=None, state_number: int=0):
    """
    Write state to file.
    """
    statefile.write_text(str(state_number))

def next_state(statefile=None, mode_count: int=0, backward: bool=False):
    """
    Cycle through states 0..n-1 forward or backward.
    """
    state_number = read_state(statefile=statefile)

    if backward:
        state_number = (state_number - 1) % mode_count
    else:
        state_number = (state_number + 1) % mode_count

    write_state(statefile=statefile, state_number=state_number)
    return state_number
