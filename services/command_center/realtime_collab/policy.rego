package realtime_collab

# Default deny
default allow = false

# Anyone can read.
allow {
    input.action == "read"
}

# Write actions require admin or editor role.
allow {
    input.action == "write"
    role := user_roles[input.user]
    role == "admin" or role == "editor"
}

# Simple user‑to‑role map mirroring the Python ``policy.py`` mapping.
user_roles = {
    "alice": "admin",
    "bob": "editor",
    "carol": "viewer",
    "test_user": "editor",
}
