import time
from datetime import datetime
import pywinauto.keyboard as keyboard
from pywinauto.application import Application
from logger import get_logger

log = get_logger()

def find_and_fill_edit(dialog, label_text, value):
    '''Finds a Static element with label_text and fills the nearest Edit element to the right'''
    try:
        # find the Static element with the specified label text
        static_elem = dialog.child_window(title_re=f'.*{label_text}.*', class_name='Static')
        static_rect = static_elem.rectangle()
        
        # find Edit elements and locate the nearest one to the right of the Static element
        candidates = []
        
        # get all children of the dialog
        all_children = list(dialog.children())
        
        for child in all_children:
            try:
                if child.class_name() == 'Edit':
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
            
    except Exception as e:
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
                time.sleep(0.01)  # Small delay between characters
            
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
    
    find_and_fill_edit(laser_setup_dialog, 'Red Lock', row.laser_red)
    find_and_fill_edit(laser_setup_dialog, 'Blue Lock', row.laser_blue)
    
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
            edit_field.set_text(target_value)
            log.ok(f"{label_text}: {target_value}")
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
    find_and_fill_edit(setup_dialog, 'Company/Institution:', config['comments_tab']['company_institution'])
    today = datetime.now().strftime("%Y-%m-%d")
    comments_with_date = f"=== Reprocessing comments === \n\nDate: {today}\n\n{row.comments}"
    comments_edit = setup_dialog.child_window(control_id=1054, class_name='Edit')
    fill_multiline_field(comments_edit, comments_with_date, clear=True)
    log.ok("Comments filled")
 
 
def setup_dialog(app, main, row, config):

    # open setup dialog
    time.sleep(1)
    main.menu_select('Process->Setup')

    log.ok("Setup Dialog should be opened now")
    
    # find setup dialog
    setup_dialog = app.window(title_re='.*Setup.*')
    setup_dialog.wait('visible', timeout=3)
    
    info_tab(setup_dialog, row)
   
    system_tab(app, setup_dialog, row)  

    config['uncertainties']['Grad. Uncert. (µGal/cm):'] = row.vgg_ste
    control_tab(app, setup_dialog, config) 

    comments_tab(setup_dialog, row, config)
   
    # Close Setup dialog by clicking OK button (Russian title 'ОК')
    time.sleep(0.5)
    ok_button = setup_dialog.child_window(control_id=1, class_name='Button')
    ok_button.click()
    log.ok("Setup dialog closed")

def run_process(app, main):
    # Start processing: Process -> Go
    log.section("Starting Processing")
    main.menu_select('Process->Go')
    log.ok("Processing started")
    
    # Check for Override Dialog and click Yes if it appears (appears immediately after Go)
    log.section("Checking Override Dialog")
    try:
        override_dialog = app.window(title_re='.*Override.*')
        override_dialog.wait('visible', timeout=3)
        log.ok("Override dialog appeared")
        yes_button = override_dialog.child_window(control_id=1, class_name='Button')
        yes_button.click()
        log.ok("Yes button clicked")
        time.sleep(2)
    except:
        log.info("[INFO] No Override dialog - continuing")

def save_project(main):
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


def run_app(df, config):

    app = Application(backend = 'win32').start(config['paths']['g9_exe'])

    time.sleep(1)

    # find main window
    main = app.window(title_re='.*Micro-g.*')
    main.wait('visible', timeout=1)

    for row in df.itertuples():

        project_path = row.fg5_file
        order = row.order
        station_id = row.station
        log.project_info(project_path, order, station_id)

        open_project(app, main, project_path)
       
        time.sleep(1)

        setup_dialog(app, main, row, config)
       
        time.sleep(2)
        
        run_process(app, main)  
        # Wait for processing to complete with timeout based on config
        log.section("Waiting for Processing to Complete")
        
        # Use timeout from config or default to 2 minutes
        max_wait_time = config.get('processing', {}).get('timeout_seconds', 120)
        log.info(f"Waiting up to {max_wait_time} seconds for processing to complete...")
        
        time.sleep(max_wait_time)
        log.ok(f"Processing timeout reached, proceeding with save and close")
        
        save_project(main)

        close_project(main)
        
    close_app(main)