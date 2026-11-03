"""Reset the memory DB and seed two past excuses for 'my manager'."""
import os

from memory import DB_PATH, save_excuse

if os.path.exists(DB_PATH):
    os.remove(DB_PATH)
save_excuse("my manager", "My dentist moved my appointment to 3pm.", 2)
save_excuse("my manager", "Our building's fire alarm test overran.", 2)
print("seeded")
