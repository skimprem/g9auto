import time
import os
import re
from datetime import datetime
import pandas as pd
import pywinauto.keyboard as keyboard
from pywinauto.application import Application
from g9auto.logger import get_logger
from g9auto.loader import read_project
from g9auto.gradient import vgg_from_quadratic, vgg_ste_from_quadratic
from g9auto.params import resolve_g9_params

log = get_logger()


def wait_main_enabled(main, timeout=30.0, poll=0.2):
    """Wait until main g9 window is enabled for menu actions."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            if main.is_enabled():
                return True
        except Exception:
            pass
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
            except Exception:
                pass

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
            except:
                pass

        if candidates:
            # Choose the candidate with the smallest distance
            candidates.sort(key=lambda x: x[0])
            closest_edit = candidates[0][1]

            closest_edit.set_text(str(value))
            return True
        else:
            return False

    except Exception:
        return False


def fill_multiline_field(edit_control, text, clear=False):
    """Fill field with multiline text - add new content with line breaks and separator"""
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
        log.info(f"Filling {len(lines)} lines of text")

        # Type each line character by character, handling spaces explicitly
        for i, line in enumerate(lines):
            log.debug(f"Line {i}: {line[:50] if len(line) > 50 else line}")

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
    time.sleep(1)
    main.menu_select('Project->&Open Project...')

    time.sleep(1)

    # find dialog for opening file by class (standard dialog class)
    file_dialog = app.window(class_name='#32770')
    file_dialog.wait('visible', timeout=5)
    log.ok("File dialog opened")

    # try to find ComboBox Edit control
    edit_controls = file_dialog.child_window(class_name='Edit')
    edit_controls.set_text(project_path)
    log.ok("Path entered")

    # Enter key or click Open/OK button
    time.sleep(1)
    keyboard.send_keys('{ENTER}')
    time.sleep(1)
    log.ok("File opened")


def info_tab(setup_dialog, row):
    # go to Information tab if it exists
    info_tab = setup_dialog.child_window(title_re='.*Information.*')
    info_tab.click()
    time.sleep(1)
    log.ok("Transitioned to Information tab")

    # fill fields from DataFrame
    log.section("Filling Fields")
    find_and_fill_edit(setup_dialog, 'Name:', row.station)
    find_and_fill_edit(setup_dialog, 'Code:', row.point)
    find_and_fill_edit(setup_dialog, 'Latitude', row.latitude)
    find_and_fill_edit(setup_dialog, 'Longitude', row.longitude)
    find_and_fill_edit(setup_dialog, 'Elevation', row.elevation)
    find_and_fill_edit(setup_dialog, 'Gradient', row.vgg)
    find_and_fill_edit(setup_dialog, 'Transfer Height', row.transfer_height)
    find_and_fill_edit(setup_dialog, 'Polar X', row.polar_x)
    find_and_fill_edit(setup_dialog, 'Polar Y', row.polar_y)

    log.info("Filled fields:\n" + "\n".join([
        f"\tName='{row.station}'",
        f"\tCode='{row.point}'",
        f"\tLatitude={row.latitude}",
        f"\tLongitude={row.longitude}",
        f"\tElevation={row.elevation}",
        f"\tGradient={row.vgg}",
        f"\tTransfer Height={row.transfer_height}",
        f"\tPolar X={row.polar_x}",
        f"\tPolar Y={row.polar_y}",
    ]))

    log.ok("All fields filled")

    # click "Set" button
    time.sleep(0.5)
    set_button = setup_dialog.child_window(title='Set', class_name='Button')
    set_button.click()
    log.ok("\"Set\" button clicked")

    time.sleep(1)


def system_tab(app, setup_dialog, row):
    # Transition to System tab - find tab control and select the desired tab
    system_tab = setup_dialog.child_window(class_name='SysTabControl32')
    # Choose System tab (index 1, as Information - 0)
    system_tab.select(1)  # 1 = System tab
    log.ok("Transitioned to System tab")

    time.sleep(1)

    log.section("Working with Laser")

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
    log.section("Filling Laser Parameters")

    find_and_fill_edit(laser_setup_dialog, 'Red Lock', row.red)
    find_and_fill_edit(laser_setup_dialog, 'Blue Lock', row.blue)

    time.sleep(0.5)

    # close L Series dialog (try OK button first, then Close)
    log.section("Closing L Series Dialog")
    ok_button = laser_setup_dialog.child_window(title='OK', class_name='Button')
    ok_button.click()

    time.sleep(2)

    # return to Setup dialog and click Advanced button on System tab
    log.section("Working with Advanced on System Tab")
    advanced_button = setup_dialog.child_window(title='Advanced...', class_name='Button')
    advanced_button.click()
    log.ok("Advanced button clicked")

    time.sleep(2)

    advanced_dialog = app.window(title_re='.*Advanced.*')
    advanced_dialog.wait('visible', timeout=5)
    log.ok("Advanced Settings dialog opened")

    time.sleep(1)

    # find and fill Clock Frequency field
    log.section("Filling Clock Frequency")
    find_and_fill_edit(advanced_dialog, 'Clock Frequency', row.frequency)

    time.sleep(0.5)

    ok_button = advanced_dialog.child_window(title='OK', class_name='Button')
    ok_button.click()
    log.ok("Advanced Settings dialog closed")

    time.sleep(1)


def control_tab(app, setup_dialog, config):
    # go to control tab
    log.section("Transitioning to Control Tab")
    tab_control = setup_dialog.child_window(class_name='SysTabControl32')
    tab_control.select(3)  # 3 = Control tab (Information=0, System=1, Acquisition=2, Control=3)
    log.ok("Control tab opened")

    time.sleep(1)

    # Press the Setup button in the Corrections group
    log.section("Opening Corrections Setup")
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

    log.section("Setting Checkbox States")
    all_controls = list(corrections_dialog.children())

    for checkbox_name, should_be_checked in checkboxes_to_check.items():
        checkbox = None
        for control in all_controls:
            try:
                if control.class_name() == 'Button' and control.window_text() == checkbox_name:
                    checkbox = control
                    break
            except:
                pass

        if checkbox:
            # Check the current state of the checkbox
            try:
                is_checked = checkbox.is_checked()
                log.debug(f"  '{checkbox_name}': current state = {is_checked}, needed = {should_be_checked}")
                if is_checked != should_be_checked:
                    checkbox.click()
                    log.ok(f"  {checkbox_name}")
                    time.sleep(0.3)
            except Exception as e:
                log.fail(f"  {checkbox_name}: {e}")
        else:
            log.fail(f"  {checkbox_name} not found")

    log.section("Filling Edit Fields")
    # Fill Edit fields with values from config
    correction_values = config['corrections']['values']

    # Collect all Edit fields
    edit_fields = []
    for control in all_controls:
        try:
            if control.class_name() == 'Edit':
                rect = control.rectangle()
                edit_fields.append((rect.top, control))
        except:
            pass

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
    log.section("Closing Corrections")
    ok_button = corrections_dialog.child_window(title='OK', class_name='Button')
    ok_button.click()
    log.ok("Corrections dialog closed")

    time.sleep(1)

    # Uncheck System Response Compensation if set
    log.section("Checking System Response Compensation")
    sys_response_checkbox = setup_dialog.child_window(title='System Response Compensation', class_name='Button')
    if sys_response_checkbox.is_checked():
        sys_response_checkbox.click()
        log.ok("System Response Compensation unchecked")
        time.sleep(0.3)
    else:
        log.ok("System Response Compensation already unchecked")

    # Press the Setup button in the Uncertainty group
    log.section("Opening Uncertainties")
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
    log.section("Filling Uncertainties")
    uncertainties_values = config['uncertainties']
    for label_text, target_value in uncertainties_values.items():
        ctrl_id = label_to_ctrl_id.get(label_text)
        if ctrl_id:
            edit_field = uncertainties_dialog.child_window(control_id=ctrl_id, class_name='Edit')
            edit_field.set_text(target_value)
            log.ok(f"{label_text}: {target_value}")
            time.sleep(0.2)
        else:
            log.fail(f"Unknown label: '{label_text}'")

    # Press Update and close the dialog
    log.section("Closing Uncertainties dialog")
    time.sleep(1)

    uncertainties_dialog.child_window(control_id=1382, class_name='Button').click()
    log.ok("'Update' button pressed")
    time.sleep(1)

    uncertainties_dialog.child_window(control_id=1, class_name='Button').click()
    log.ok("'Uncertainties' dialog closed")
    time.sleep(2)


def comments_tab(setup_dialog, row, config):
    # Transition to Comments tab
    log.section("Transitioning to Comments Tab")
    time.sleep(1)
    setup_dialog.set_focus()
    time.sleep(0.5)
    tab_control = setup_dialog.child_window(class_name='SysTabControl32')
    tab_control.select(4)  # 4 = Comments tab
    log.ok("Comments tab opened")
    time.sleep(1)

    # Fill fields on the Comments tab
    log.section("Filling Comments")
    # find_and_fill_edit(setup_dialog, 'Instrument Operator:', config['comments_tab']['operator'])
    find_and_fill_edit(setup_dialog, 'Company/Institution:', config['comments_tab']['institution'])
    today = datetime.now().strftime("%Y-%m-%d")
    comments_with_date = f"=== Reprocessing comments === \n\nDate: {today}\n\n{config['comments_tab']['comments']}"
    comments_edit = setup_dialog.child_window(control_id=1054, class_name='Edit')
    fill_multiline_field(comments_edit, comments_with_date, clear=True)
    log.ok("Comments filled")


def setup_dialog(app, main, row, config):
    if not wait_main_enabled(main):
        log.warning("Main window did not become enabled before opening Setup")

    # open setup dialog
    time.sleep(1)
    main.menu_select('Process->Setup')

    log.ok("Setup Dialog should be opened now")

    # find setup dialog
    dlg = app.window(title_re='.*Setup.*')
    dlg.wait('visible', timeout=3)

    info_tab(dlg, row)

    system_tab(app, dlg, row)

    config['uncertainties']['Grad. Uncert. (µGal/cm):'] = row.vgg_ste
    control_tab(app, dlg, config)

    comments_tab(dlg, row, config)

    # Close Setup dialog by clicking OK button
    time.sleep(0.5)
    ok_button = dlg.child_window(control_id=1, class_name='Button')
    ok_button.click()
    log.ok("Setup dialog closed")


def run_process(main):
    if not wait_main_enabled(main):
        log.warning("Main window did not become enabled before Process->Go")

    # Start processing: Process -> Go
    log.section("Starting Processing")
    main.menu_select('Process->Go')
    log.ok("Processing started")


def overwrite_report(app, file_name=None):
    # Check for Override Dialog and click Yes if it appears (appears immediately after Go)
    log.section("Checking Override Dialog")
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
            log.info(f'Entering file name: {file_name}')
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
        log.info("[INFO] No Override dialog - continuing")


def save_project(main):
    if not wait_main_enabled(main):
        log.warning("Main window did not become enabled before Project->Save")

    # Save project
    log.section("Saving")
    time.sleep(1)
    main.menu_select('Project->Save')
    log.ok("Saved")


def close_project(main):
    time.sleep(2)
    log.section("Closing")
    main.menu_select('Project->Close')
    log.ok("Closed")
    time.sleep(2)


def close_app(main):
    # Close the application
    log.section("Shutting Down")
    time.sleep(1)
    main.close()
    log.ok("Application closed")
    log.success("All projects processed!")


def _as_int(value):
    try:
        result = int(value)
        return result
    except (TypeError, ValueError):
        return None


def _report_txt_path(project_path, report_name=None):
    if report_name:
        return os.path.join(os.path.dirname(project_path), f"{report_name}.project.txt")
    return os.path.splitext(project_path)[0] + '.project.txt'

def _run_single_pass(app, main, row, config, max_wait_time, vgg_value, vgg_ste_value, transfer_height_cm, report_file=None):
    row_local = row.copy()
    row_local['vgg'] = vgg_value
    row_local['vgg_ste'] = vgg_ste_value
    row_local['transfer_height'] = transfer_height_cm

    setup_dialog(app, main, row_local, config)

    time.sleep(2)
    run_process(main)
    time.sleep(2)

    overwrite_report(app, report_file)

    log.section("Waiting for Processing to Complete")
    log.info(f"Waiting up to {max_wait_time} seconds for processing to complete...")
    time.sleep(max_wait_time)
    log.ok("Processing timeout reached, proceeding with save")
    save_project(main)


def run_app(df, config):

    result = []

    app = Application(backend='win32').start(config['paths']['g9_exe'])

    time.sleep(1)

    # find main window
    main = app.window(title_re='.*Micro-g.*')
    main.wait('visible', timeout=1)

    for _, row in df.iterrows():

        project_path = row.fg5_file
        station_id = row.station
        log.project_info(project_path, station_id)

        open_project(app, main, project_path)

        time.sleep(1)

        # Use timeout from config or default to 1 minute
        max_wait_time = _as_int(getattr(config.get('processing', {}), 'timeout_seconds', None)) or 60

        # transfer_height = _as_float(getattr(row, 'transfer_height', None))
        # setup_height = _as_float(getattr(row, 'setup_height', None))
        # h_eff_plate = _as_float(getattr(row, 'h_eff_plate', None))
        # vgg = _as_float(getattr(row, 'vgg', None))
        # vgg_ste = _as_float(getattr(row, 'vgg_ste', None))
        # a = _as_float(getattr(row, 'a', None))
        # b = _as_float(getattr(row, 'b', None))
        # ua = _as_float(getattr(row, 'ua', None))
        # ub = _as_float(getattr(row, 'ub', None))
        # covab = _as_float(getattr(row, 'covab', None))

        base_name = os.path.splitext(os.path.basename(project_path))[0]
        # instrument = config.get('gravimeter', {}).get('type', 'A10')
        # default_plate_cm = _as_float(
        #     config.get('gravimeter', {}).get('effective_height_cm', {}).get(instrument, 68.3)
        # )

        # If h_eff_plate is known, two-pass is not needed.
        # if input_plate_cm is not None and vgg is not None and transfer_height is not None:

       
        # if vgg is None:
            # vgg = vgg_from_quadratic(a, b, ua, ub, covab, transfer_height)
            # log.info(f"vgg is missing: computed from quadratic coefficients as {vgg:.3f} µGal/cm")

        # transfer_height priority and fallback logic:
        # 1) if transfer_height is provided -> use it;
        # 2) if missing -> compute from h_eff_plate + setup_height;
        # 3) if h_eff_plate is missing -> use near-constant fallback from config (68.3 cm by default).
        # if transfer_height is None:
        #     if setup_height is None:
        #         log.fail(
        #             "setup_height is required when transfer_height is missing"
        #         )
        #         close_project(main)
        #         continue

        #     if h_eff_plate is None:

        #         # Derive effective height from two runs when h_eff is unknown:
        #         # 1) run with vgg = 0.0
        #         # 2) run with vgg = -3.086
        #         # h_eff_plate_cm = (gravity(-3.086) - gravity(0)) / -3.086
        #         # Final run uses gradient between h_eff_plate and transfer_height.

        #         log.info("h_eff_plate is missing with explicit transfer_height: enabling two-pass mode (vgg=0 and vgg=-3.086)")
        #         vgg_zero = 0.0
        #         vgg_ref = -3.086
        #         report_0 = f"{base_name}_0"
        #         report_vgg = f"{base_name}_vgg"

        #         if not os.path.exists(f"{report_0}.project.txt") and not os.path.exists(f"{report_vgg}.project.txt"):
        #             _run_single_pass(app, main, row, config, max_wait_time, vgg_zero, 0.03, 0.0, report_file=report_0)
        #             _run_single_pass(app, main, row, config, max_wait_time, vgg_ref, 0.03, 0.0, report_file=report_vgg)

        #         project_0, _ = read_project(_report_txt_path(project_path, report_0))
        #         result.append(project_0)
        #         gravity_0 = project_0[('Processing Results', 'Gravity', 'µGal')]
        #         project_vgg, _ = read_project(_report_txt_path(project_path, report_vgg))
        #         gravity_vgg = project_vgg[('Processing Results', 'Gravity', 'µGal')]

        #         h_eff_plate = setup_height + (gravity_0 - gravity_vgg) / vgg_ref
    
        #     plate_for_transfer_cm = h_eff_plate if h_eff_plate is not None else default_plate_cm
        #     transfer_height = plate_for_transfer_cm + setup_height
        #     if h_eff_plate is not None:
        #         log.info(
        #             f"transfer_height is missing: computed as h_eff_plate + setup_height = "
        #             f"{plate_for_transfer_cm:.3f} + {setup_height:.3f} = {transfer_height:.3f} cm"
        #         )
        #     else:
        #         log.info(
        #             f"transfer_height is missing: computed from default h_eff_plate={plate_for_transfer_cm:.3f} cm "
        #             f"and setup_height={setup_height:.3f} cm -> {transfer_height:.3f} cm"
        #         )
 
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
        h_eff_plate = params['h_eff_plate']

        _run_single_pass(app, main, row, config, max_wait_time, vgg, vgg_ste, transfer_height, report_file=None)

        project_result = read_project(_report_txt_path(project_path))[0]
        result.append(project_result)

        close_project(main)

    close_app(main)

    return pd.DataFrame(result)