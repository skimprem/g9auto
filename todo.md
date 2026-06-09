# TODO

## High Priority

### Replace fixed sleeps with explicit waits

The current GUI automation relies heavily on `time.sleep()`, which makes the workflow sensitive to system performance and application response times.

Tasks:

* Replace `time.sleep()` with `pywinauto` wait methods where possible.
* Use `wait("visible")`, `wait("enabled")`, and similar state-based checks.
* Create reusable helper functions for waiting on dialogs and controls.
* Minimize arbitrary delays.

Expected result:

* More reliable automation.
* Faster execution on responsive systems.
* Better compatibility across different machines.

---

### Capture screenshots on failures

GUI automation failures can be difficult to diagnose from logs alone.

Tasks:

* Automatically capture screenshots when exceptions occur.

* Save screenshots to:

  ```
  logs/screenshots/
  ```

* Include timestamps in filenames.

* Log the screenshot path together with the error message.

Expected result:

* Easier troubleshooting.
* Faster identification of unexpected dialogs or UI changes.

---

### Improve startup logging

Provide more visibility into application startup and configuration.

Tasks:

* Log the configuration file path.
* Log active logging settings.
* Log execution mode (single site or batch processing).
* Log the number of loaded projects.
* Log processing start and completion.

Expected result:

* Easier diagnosis of configuration issues.
* Better reproducibility.

---

## Medium Priority

### Centralize GUI control identifiers

Many GUI controls are currently referenced using raw numeric IDs.

Tasks:

* Create a dedicated module or class containing all control IDs.
* Replace hardcoded values with named constants.

Example:

```python
LASER_SETUP_BUTTON = 1029
CORRECTIONS_SETUP_BUTTON = 1454
UNCERTAINTIES_SETUP_BUTTON = 1241
```

Expected result:

* Improved readability.
* Easier maintenance after g9 updates.

---

### Log g9auto version

Tasks:

* Display the current g9auto version during startup.
* Include version information in log files.

Example:

```text
[INFO] g9auto version 0.4.1
```

Expected result:

* Easier debugging across different installations.

---

### Log g9 version

Tasks:

* Detect and log the installed g9 version.
* Record the version at startup.

Expected result:

* Easier identification of compatibility issues after g9 updates.

---

### Add dry-run mode

Provide a mode that validates input without launching g9.

Example:

```bash
g9auto run --data sites.csv --dry-run
```

Tasks:

* Load configuration.
* Load and validate project list.
* Apply station filtering.
* Display projects that would be processed.
* Exit without starting g9.

Expected result:

* Safer testing and validation of batch jobs.

---

## Low Priority

### Add type hints

Tasks:

* Add missing type annotations.
* Improve IDE support and static analysis.

Expected result:

* Better code navigation.
* Easier maintenance.

---

### Introduce a G9Application class

As the project grows, GUI automation logic should be encapsulated.

Possible structure:

```python
class G9Application:
    def open_project(...)
    def setup(...)
    def process(...)
    def save(...)
    def close(...)
```

Expected result:

* Better separation of concerns.
* Easier future extension.
* Cleaner code organization.

---

## Long-Term Goal

The primary purpose of g9auto is to provide reliable automation of the proprietary Micro-g LaCoste g9 software until full processing functionality becomes available in AGP (Absolute Gravimeter Processing).

Future development effort should therefore focus on:

1. Reliability.
2. Diagnostics and logging.
3. Maintainability.

Avoid large architectural changes unless they directly improve these goals.
