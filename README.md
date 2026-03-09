# PomoScheduler

**PomoScheduler** is a terminal-based Pomodoro timer and task management system. It combines a persistent background daemon with a highly legible Terminal User Interface (TUI), allowing you to manage focus sessions without keeping a terminal window permanently open.

The system enforces **single-task focus**: it is only possible to run one task at a time. The timer executes asynchronously, meaning it will continue running in the background even if you close the terminal application entirely.

---

# Architecture

The application is split into two primary components:

## The Engine (Daemon)
A lightweight background process that:
- Manages the countdown state
- Handles phase transitions (Focus, Short Break, Long Break)
- Dispatches native system notifications

## The Client (TUI / CLI)
A user-friendly dashboard built with **Textual**. It communicates with the daemon to display live progress via a custom-built, large-scale digital clock font.

The Client also provides a fast CLI for executing commands without launching the full visual dashboard. This can be used to let agents or scripts interact with the timer programmatically.

---

# Features

### Asynchronous Daemon
The timer runs completely independent of the UI.

### Task Management
Create, edit, and delete tasks with assigned Pomodoro estimates directly from the TUI.

### Repeating Blueprints
Set up recurring rules for daily or days in week tasks that automatically populate your active queue.

### Scheduled Auto-Start
Configure tasks to start automatically at a specific time (e.g., starting a routine at **9:00 AM**).

The daemon will automatically transition to the designated task and trigger a notification, eliminating the need to interact with the TUI to begin your work.

### System Notifications
Desktop alerts notify you precisely when it is time to switch contexts between work and break phases.

---

# Installation

Ensure you have **uv** installed on your system:

https://github.com/astral-sh/uv

### Clone the repository

```bash
git clone https://github.com/Sidharth-Darwin/PomoScheduler.git
cd pomoscheduler
```

### Install the application globally using uv

```bash
uv tool install .
```

### Refresh your shell cache to recognize the new `pomo` command (useful if you are repeating the installation process):

```bash
hash -r
```

---

# Usage

Once installed, the `pomo` command will be available globally across your system.

### Launch the TUI

```bash
pomo tui
```

### Start a task

```bash
pomo start <task_id>
```

### Stop the current session

```bash
pomo stop
```

### Check timer status

```bash
pomo status
```

---

# Configuration

Settings can be adjusted directly within the **TUI** by clicking the **Settings** button.

From there you can configure:

- Focus session duration
- Short break duration
- Long break duration
- Pomodoro interval before a long break is triggered
- Sound and notification preferences (path to custom alert sounds can be set here as well)