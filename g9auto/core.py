import time
import os
from datetime import datetime
import pandas as pd
import pywinauto.keyboard as keyboard
from pywinauto.application import Application
from g9auto.logger import get_logger
from g9auto.loader import read_project
from g9auto.params import resolve_g9_params

log = get_logger()


def wait_main_enabled(main, timeout=30.0, poll=0.2):
    '''Wait until main g9 window is enabled for menu actions.'''
    start = time.time()
    while time.time() - start < timeout:
        try:
            if main.is_enabled():
                return True
        except Exception as e:
            log.error(f"Exception while waiting for main window to be enabled: {e}")
        time.sleep(poll)
    return False


def find_and_fill_edit(dialog, label_text, value):
    '''Finds a Static element with label_text and fills the nearest Edit element to the right'''
    try:
        # Find visible Static labels only (tab pages often contain hidden duplicates).
        label_text_l = str(label_text).lower()
        static_candidates = []
        for child in dialog.children():
            try:
                if child.class_name() != 'Static':
                    continue
                if not child.is_visible():
                    continue
                text = child.window_text() or ''
                if label_text_l in text.lower():
                    rect = child.rectangle()
                    static_candidates.append((rect.top, rect.left, child))
            except Exception as e:
                log.error(f"Error processing child control: {child}, Exception: {e}")

        if not static_candidates:
            return False

        # Prefer top-left label among visible matches for deterministic behavior.
        static_candidates.sort(key=lambda x: (x[0], x[1]))
        static_elem = static_candidates[0][2]
        static_rect = static_elem.rectangle()

        # find Edit elements and locate the nearest one to the right of the Static element
        candidates = []

        # get all children of the dialog
        all_children = list(dialog.children())

        for child in all_children:
            try:
                if child.class_name() == 'Edit':
                    if not child.is_visible():
                        continue
                    child_rect = child.rectangle()

                    # check if the Edit is to the right and on the same row as the Static element
                    same_row = abs(child_rect.top - static_rect.top) < 12
                    is_to_the_right = child_rect.left > static_rect.right

                    if same_row and is_to_the_right:
                        distance = child_rect.left - static_rect.right
                        candidates.append((distance, child))
            except Exception as e:
                log.error(f"Error processing child control: {child}, Exception: {e}")

        if candidates:
            # Choose the candidate with the smallest distance
            candidates.sort(key=lambda x: x[0])
            closest_edit = candidates[0][1]

            closest_edit.set_text(str(value))
            return True
        else:
            return False

    except Exception as e:
        log.error(f"Exception in find_and_fill_edit: {e}")
        return False


def fill_multiline_field(edit_control, text, clear=False):
    '''Fill field with multiline text - add new content with line breaks and separator'''
    try:
        if clear:
            edit_control.set_text('')  # Clear existing text
            time.sleep(0.3)

        # Click on the field to ensure it has focus
        edit_control.click()
        time.sleep(0.3)

        # Move to the end of the field
        keyboard.send_keys('^{END}')
        time.sleep(0.2)

        # Add one line break
        keyboard.send_keys('^{ENTER}')
        time.sleep(0.2)

        # Add another line break
        keyboard.send_keys('^{ENTER}')
        time.sleep(0.3)

        # Split by lines
        lines = text.split('\n')
        log.ok(f"Filling {len(lines)} lines of text")

        # Type each line character by character, handling spaces explicitly
        for i, line in enumerate(lines):
            log.ok(f"Line {i}: {line[:50] if len(line) > 50 else line}")

            # Type each character, converting spaces to {SPACE}
            for char in line:
                if char == ' ':
                    keyboard.send_keys('{SPACE}')
                else:
                    keyboard.send_keys(char)

            time.sleep(0.1)

            # Add line break for all lines except the last
            if i < len(lines) - 1:
                keyboard.send_keys('^{ENTER}')  # Ctrl+Enter for line break
                time.sleep(0.1)

        log.ok("Text filled successfully")
        return True
    except Exception as e:
        log.fail(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def open_project(app, main, project_path):
    '''Open project using the main window's menu'''
    time.sleep(1)
    main.menu_select('Project->&Open Project...')

    time.sleep(1)

    # find dialog for opening file by class (standard dialog class)
    file_dialog = app.window(class_name='#32770')
    file_dialog.wait('visible', timeout=5)
    log.debug("File Dialog Opened")

    # try to find ComboBox Edit control
    edit_controls = file_dialog.child_window(class_name='Edit')
    edit_controls.set_text(project_path)
    log.debug("Path entered")

    # Enter key or click Open/OK button
    time.sleep(1)
    keyboard.send_keys('{ENTER}')
    time.sleep(1)
    log.debug("File opened")


def info_tab(setup_dialog, row):
    '''Fill Information tab with data from DataFrame row'''
    # go to Information tab if it exists
    info_tab_dialog = setup_dialog.child_window(title_re='.*Information.*')
    info_tab_dialog.click()
    time.sleep(1)
    log.section("Information Tab")

    # fill fields from DataFrame
    find_and_fill_edit(setup_dialog, 'Name:', row.site)
    log.ok(f"Name: {row.site}")
    find_and_fill_edit(setup_dialog, 'Code:', row.code)
    log.ok(f"Code: {row.code}")
    find_and_fill_edit(setup_dialog, 'Latitude', row.latitude)
    log.ok(f"Latitude: {row.latitude:.6f}")
    find_and_fill_edit(setup_dialog, 'Longitude', row.longitude)
    log.ok(f"Longitude: {row.longitude:.6f}")
    find_and_fill_edit(setup_dialog, 'Elevation', row.elevation)
    log.ok(f"Elevation: {row.elevation:.1f}")
    find_and_fill_edit(setup_dialog, 'Gradient', row.vgg)
    log.ok(f"Gradient: {row.vgg:.3f}")
    find_and_fill_edit(setup_dialog, 'Transfer Height', row.transfer_height)
    log.ok(f"Transfer Height: {row.transfer_height}")
    find_and_fill_edit(setup_dialog, 'Polar X', row.polar_x)
    log.ok(f"Polar X: {row.polar_x:.3f}")
    find_and_fill_edit(setup_dialog, 'Polar Y', row.polar_y)
    log.ok(f"Polar Y: {row.polar_y:.3f}")

    # click "Set" button
    time.sleep(0.5)
    set_button = setup_dialog.child_window(title='Set', class_name='Button')
    set_button.click()
    log.ok("\"Set\" button clicked")

    time.sleep(1)


def system_tab(app, setup_dialog, row):
    '''Fill System tab with data from DataFrame row'''
    # Transition to System tab - find tab control and select the desired tab
    system_tab_dialog = setup_dialog.child_window(class_name='SysTabControl32')
    # Choose System tab (index 1, as Information - 0)
    system_tab_dialog.select(1)  # 1 = System tab
    log.section("System Tab")

    time.sleep(1)

    # find the Laser button (Group)
    setup_button = setup_dialog.child_window(control_id=1029, class_name='Button')
    setup_button.click()
    log.ok("Laser Setup button pressed")

    time.sleep(1)

    laser_setup_dialog = app.window(title_re='.*L Series.*')
    laser_setup_dialog.wait('visible', timeout=5)
    log.ok("L Series dialog opened")

    time.sleep(1)

    # find and fill fields Red Lock and Blue Lock in the Wavelengths group
    find_and_fill_edit(laser_setup_dialog, 'Red Lock', row.red)
    log.ok(f"Red Lock: {row.red:.8f}")
    find_and_fill_edit(laser_setup_dialog, 'Blue Lock', row.blue)
    log.ok(f"Blue Lock: {row.blue:.8f}")

    time.sleep(0.5)

    # close L Series dialog (try OK button first, then Close)
    ok_button = laser_setup_dialog.child_window(title='OK', class_name='Button')
    ok_button.click()
    log.ok("L Series dialog closed with OK button")

    time.sleep(2)

    # return to Setup dialog and click Advanced button on System tab
    advanced_button = setup_dialog.child_window(title='Advanced...', class_name='Button')
    advanced_button.click()
    log.ok("Advanced button clicked")

    time.sleep(2)

    advanced_dialog = app.window(title_re='.*Advanced.*')
    advanced_dialog.wait('visible', timeout=5)
    log.ok("Advanced Settings dialog opened")

    time.sleep(1)

    # find and fill Clock Frequency field
    find_and_fill_edit(advanced_dialog, 'Clock Frequency', row.frequency)
    log.ok(f"Clock Frequency: {row.frequency:.6f}")

    time.sleep(0.5)

    ok_button = advanced_dialog.child_window(title='OK', class_name='Button')
    ok_button.click()
    log.ok("Advanced Settings dialog closed")

    time.sleep(1)


def control_tab(app, setup_dialog, config):
    '''Fill Control tab with data from config'''
    # go to control tab
    tab_control = setup_dialog.child_window(class_name='SysTabControl32')
    tab_control.select(3)  # 3 = Control tab (Information=0, System=1, Acquisition=2, Control=3)
    log.section("Control Tab")

    time.sleep(1)

    # Press the Setup button in the Corrections group
    setup_button = setup_dialog.child_window(control_id=1454, class_name='Button')
    setup_button.click()
    log.ok("Corrections Setup button pressed")

    time.sleep(2)

    # Find the Corrections Setup dialog
    corrections_dialog = app.window(title_re='.*Corrections.*')
    corrections_dialog.wait('visible', timeout=5)
    log.ok("Corrections Setup dialog opened")

    time.sleep(1)

    # Determine which checkboxes should be checked
    checkboxes_to_check = config['corrections']['checkboxes']

    all_controls = list(corrections_dialog.children())

    for checkbox_name, should_be_checked in checkboxes_to_check.items():
        checkbox = None
        for control in all_controls:
            try:
                if control.class_name() == 'Button' and control.window_text() == checkbox_name:
                    checkbox = control
                    break
            except Exception:
                pass

        if checkbox:
            # Check the current state of the checkbox
            try:
                is_checked = checkbox.is_checked()
                if is_checked != should_be_checked:
                    checkbox.click()
                    log.ok(f"{checkbox_name}: {should_be_checked}")
                    time.sleep(0.3)
            except Exception as e:
                log.fail(f"{checkbox_name}: {e}")
        else:
            log.fail(f"{checkbox_name} not found")

    # Fill Edit fields with values from config
    correction_values = config['corrections']['values']

    # Collect all Edit fields
    edit_fields = []
    for control in all_controls:
        try:
            if control.class_name() == 'Edit':
                rect = control.rectangle()
                edit_fields.append((rect.top, control))
        except Exception as e:
            log.error(f"Error processing child control: {control}, Exception: {e}")

    # Sort by vertical position (top to bottom)
    edit_fields.sort(key=lambda x: x[0])

    # Fill Edit fields in order:
    # 1. Baro. Fact (first Edit)
    # 2. Self Attraction Correction (second Edit)
    # 3. Diffraction Correction (third Edit)
    mapping = [
        ('Baro. Fact', 0),
        ('Self Attraction Correction', 1),
        ('Diffraction Correction', 2),
    ]

    for label_text, index in mapping:
        edit_field = edit_fields[index][1]
        target_value = correction_values.get(label_text, '')
        if target_value:
            try:
                edit_field.set_text(target_value)
                log.ok(f"{label_text}: {target_value}")
            except Exception as e:
                log.fail(f"{label_text}: {e}")
        time.sleep(0.2)

    # Close the dialog
    ok_button = corrections_dialog.child_window(title='OK', class_name='Button')
    ok_button.click()
    log.ok("Corrections dialog closed")

    time.sleep(1)

    # Uncheck System Response Compensation if set
    sys_response_checkbox = setup_dialog.child_window(title='System Response Compensation', class_name='Button')
    if sys_response_checkbox.is_checked():
        sys_response_checkbox.click()
        log.ok("System Response Compensation unchecked")
        time.sleep(0.3)
    else:
        log.ok("System Response Compensation already unchecked")

    # Press the Setup button in the Uncertainty group
    setup_dialog.child_window(control_id=1241, class_name='Button').click()
    log.ok("Uncertainties Setup button pressed")

    time.sleep(2)

    uncertainties_dialog = app.window(title_re='.*Uncertainties.*')
    uncertainties_dialog.wait('visible', timeout=5)
    log.ok("Uncertainties dialog opened")

    time.sleep(1)

    # Mapping: label from config -> control_id of Edit field
    label_to_ctrl_id = {
        'Earth Tides Factor:': 1003,
        'Ocean Load Factor:': 1004,
        'Barometric (µGal):': 1005,
        'Polar Motion (µGal):': 1006,
        'Laser (µGal):': 1007,
        'Clock (µGal):': 1008,
        'System Model (µGal):': 1009,
        'Tide Swell (µGal):': 1010,
        'Water Table (µGal):': 1011,
        'Unmodeled (µGal):': 1012,
        'System (µGal):': 1013,
        'Grad. Uncert. (µGal/cm):': 1014,
        'Gradient (µGal):': 1380,
    }

    # Fill Uncertainties fields according to config
    uncertainties_values = config['uncertainties']
    for label_text, target_value in uncertainties_values.items():
        ctrl_id = label_to_ctrl_id.get(label_text)
        if ctrl_id:
            edit_field = uncertainties_dialog.child_window(control_id=ctrl_id, class_name='Edit')
            edit_field.set_text(target_value)
            log.ok(f"{label_text} {target_value}")
            time.sleep(0.2)
        else:
            log.fail(f"Unknown label: '{label_text}'")

    # Press Update and close the dialog
    time.sleep(1)

    uncertainties_dialog.child_window(control_id=1382, class_name='Button').click()
    log.ok("'Update' button pressed")
    time.sleep(1)

    uncertainties_dialog.child_window(control_id=1, class_name='Button').click()
    log.ok("'Uncertainties' dialog closed")
    time.sleep(2)


def comments_tab(setup_dialog, config):
    '''Fill Comments tab with data from config'''
    # Transition to Comments tab
    time.sleep(1)
    setup_dialog.set_focus()
    time.sleep(0.5)
    tab_control = setup_dialog.child_window(class_name='SysTabControl32')
    tab_control.select(4)  # 4 = Comments tab
    log.section("Comments Tab")
    time.sleep(1)

    # Fill fields on the Comments tab
    find_and_fill_edit(setup_dialog, 'Instrument Operator:', config['comments_tab']['operator'])
    log.ok(f"Operator: {config['comments_tab']['operator']}")
    find_and_fill_edit(setup_dialog, 'Company/Institution:', config['comments_tab']['institution'])
    log.ok(f"Institution: {config['comments_tab']['institution']}")
    today = datetime.now().strftime("%Y-%m-%d")
    comments_with_date = f"=== Reprocessing comments === \n\nDate: {today}\n\n{config['comments_tab']['comments']}"
    comments_edit = setup_dialog.child_window(control_id=1054, class_name='Edit')
    fill_multiline_field(comments_edit, comments_with_date, clear=True)
    log.ok("Comments filled")


def setup_dialog(app, main, row, config):
    '''Open and fill the Setup dialog with data from DataFrame row and config'''
    if not wait_main_enabled(main):
        log.warning("Main window did not become enabled before opening Setup")

    # open setup dialog
    time.sleep(1)
    main.menu_select('Process->Setup')

    log.debug("Setup Dialog Opened")

    # find setup dialog
    dlg = app.window(title_re='.*Setup.*')
    dlg.wait('visible', timeout=3)

    info_tab(dlg, row)

    system_tab(app, dlg, row)

    config['uncertainties']['Grad. Uncert. (µGal/cm):'] = row.vgg_ste
    control_tab(app, dlg, config)

    comments_tab(dlg, config)

    # Close Setup dialog by clicking OK button
    time.sleep(0.5)
    ok_button = dlg.child_window(control_id=1, class_name='Button')
    ok_button.click()
    log.debug("Setup Dialog Closed")


def run_process(main):
    '''Start processing by selecting Process->Go from the main menu'''
    if not wait_main_enabled(main):
        log.warning("Main window did not become enabled before Process->Go")

    # Start processing: Process -> Go
    main.menu_select('Process->Go')
    log.debug("Process->Go")


def overwrite_report(app, file_name=None):
    '''Handle the case when Override Dialog appears after starting processing, and optionally set a new file name'''
    log.section("Checking for Override Dialog")
    # Check for Override Dialog and click Yes if it appears (appears immediately after Go)
    try:
        override_dialog = app.window(title_re='.*Override Dialog*')
        override_dialog.wait('visible', timeout=3)
        if file_name:
            no_button = override_dialog.child_window(title='&No', class_name='Button')
            no_button.click()
            log.ok("No button clicked")
            time.sleep(1)
            change_file_name = app.window(title_re='.*Change File Name.*')
            change_file_name.wait('visible', timeout=3)
            edit_controls = change_file_name.child_window(control_id=1245)
            edit_controls.set_text(file_name)
            time.sleep(1)
            log.ok(f"File name '{file_name}' entered in Override dialog")
            ok_button = change_file_name.child_window(title='OK', class_name='Button')
            ok_button.click()
            time.sleep(1)
            log.ok("Override dialog appeared")
        yes_button = override_dialog.child_window(title='&Yes', class_name='Button')
        yes_button.click()
        log.ok("Yes button clicked")
        time.sleep(2)
    except:
        log.ok("No Override dialog - continuing")


def save_project(main):
    '''Save project using the main window's menu'''
    if not wait_main_enabled(main):
        log.warning("Main window did not become enabled before Project->Save")

    # Save project
    time.sleep(1)
    main.menu_select('Project->Save')
    log.info("Project Saved")


def close_project(main):
    '''Close project using the main window's menu'''
    time.sleep(2)
    main.menu_select('Project->Close')
    log.info("Project Closed")
    time.sleep(2)


def close_app(main):
    '''Close the application'''
    # Close the application
    time.sleep(1)
    main.close()
    log.info("Application closed")


def _as_int(value):
    '''Convert a value to an integer, returning None if conversion fails'''
    try:
        result = int(value)
        return result
    except (TypeError, ValueError):
        return None


def _report_txt_path(project_path, report_name=None):
    '''Determine the path for the report text file based on the project path and optional report name'''
    if report_name:
        return os.path.join(os.path.dirname(project_path), f"{report_name}.project.txt")
    return os.path.splitext(project_path)[0] + '.project.txt'

def _run_single_pass(app, main, row, config, max_wait_time, vgg_value, vgg_ste_value, transfer_height_cm, report_file=None):
    '''Run a single processing pass with the given parameters'''
    row_local = row.copy()
    row_local['vgg'] = vgg_value
    row_local['vgg_ste'] = vgg_ste_value
    row_local['transfer_height'] = transfer_height_cm

    setup_dialog(app, main, row_local, config)

    time.sleep(2)
    run_process(main)
    time.sleep(2)

    overwrite_report(app, report_file)

    log.info(f"Waiting up to {max_wait_time} seconds for processing to complete...")
    time.sleep(max_wait_time)
    log.info("Processing timeout reached, proceeding with save")
    save_project(main)


def run_app(df, config):
    '''Main function to run the application with the given DataFrame and configuration'''
    result = []

    app = Application(backend='win32').start(config['paths']['g9_exe'])

    time.sleep(1)

    # find main window
    main = app.window(title_re='.*Micro-g.*')
    main.wait('visible', timeout=1)

    for _, row in df.iterrows():

        project_path = row.fg5_file
        station_id = row.site
        log.project_info(project_path, station_id)

        open_project(app, main, project_path)

        time.sleep(1)

        # Use timeout from config or default to 1 minute
        max_wait_time = _as_int(getattr(config.get('processing', {}), 'timeout_seconds', None)) or 60

        base_name = os.path.splitext(os.path.basename(project_path))[0]

        params = resolve_g9_params(
            app=app,
            main=main,
            row=row,
            config=config,
            max_wait_time=max_wait_time,
            base_name=base_name,
            project_path=project_path,
            result=result,
            run_single_pass=_run_single_pass,
            report_txt_path=_report_txt_path
        )

        if params is None:
            close_project(main)
            continue

        transfer_height = params['transfer_height']
        vgg = params['vgg']
        vgg_ste = params['vgg_ste']
        # h_eff_plate = params['h_eff_plate']

        _run_single_pass(app, main, row, config, max_wait_time, vgg, vgg_ste, transfer_height, report_file=None)

        project_result = read_project(_report_txt_path(project_path))[0]
        result.append(project_result)

        close_project(main)

    close_app(main)

    return pd.DataFrame(result)