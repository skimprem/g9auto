import os
import time
from datetime import datetime
import pandas as pd
import pywinauto.keyboard as keyboard
from pywinauto.application import Application

def get_full_path(common_path, order, station_id, point_id):
    """
    Constructs and verifies the existence of the full path to a point's projects.
    Supports different point formats: 079, 79, 0079, 486, 8406, etc.
    
    Args:
        common_path (str): Base path to projects
        order (str): Order (first/zero)
        station_id (str): Station ID (3-4 letters)
        point_id (str|int): Point ID (4 letters or number from 1-9999)
    
    Returns:
        str: Full path to the point if it exists
        
    Raises:
        ValueError: If path does not exist
    """
    
    point_id_str = str(point_id).strip()
    station_path = os.path.join(common_path, f'{order}_order', f'{station_id}')
    
    # If it's lettered - look for a folder with exact match or in upper case
    if not point_id_str.isdigit():
        # Try different variants for letters
        variants = [point_id_str, point_id_str.upper(), point_id_str.lower()]
        for variant in variants:
            full_path = os.path.join(station_path, variant)
            if os.path.exists(full_path):
                return full_path
    else:
        # For numeric IDs generate variants and search for existing folders
        # Convert to number for processing
        point_num = int(point_id_str)
        
        # Generate possible folder name variants
        variants = []
        
        # Original string format
        variants.append(point_id_str)
        
        # With leading zeros to 3, 4, 5 characters
        for width in range(3, 6):
            padded = str(point_num).zfill(width)
            if padded not in variants:
                variants.append(padded)
        
        # Without leading zeros (digits only)
        stripped = str(point_num).lstrip('0') or '0'
        if stripped not in variants:
            variants.append(stripped)
        
        # Try each variant
        for variant in variants:
            full_path = os.path.join(station_path, variant)
            if os.path.exists(full_path):
                return full_path
    
    # If nothing found, show error
    raise ValueError(f"Path does not exist. Station: {station_id}, Point: {point_id}")


def get_session_folders(point_path):
    """
    Gets all session folders (YYYYMMDD) in the absolute folder of a point.
    
    Args:
        point_path (str): Full path to the point folder
    
    Returns:
        list: List of paths to session folders (YYYYMMDD)
    """
    absolute_path = os.path.join(point_path, 'absolute')
    
    if not os.path.exists(absolute_path):
        return []
    
    sessions = []
    for folder in os.listdir(absolute_path):
        folder_path = os.path.join(absolute_path, folder)
        # Check that it's a folder and the name matches YYYYMMDD format (8 digits)
        if os.path.isdir(folder_path) and folder.isdigit() and len(folder) == 8:
            sessions.append(folder_path)
    
    return sorted(sessions)


def get_fg5_files(session_path):
    """
    Gets all *.fg5 files from the raw folder of a session.
    
    Args:
        session_path (str): Full path to the session folder (YYYYMMDD)
    
    Returns:
        list: List of paths to *.fg5 files
    """
    raw_path = os.path.join(session_path, 'raw')
    
    if not os.path.exists(raw_path):
        return []
    
    fg5_files = []
    for file in os.listdir(raw_path):
        if file.endswith('.fg5'):
            fg5_path = os.path.join(raw_path, file)
            fg5_files.append(fg5_path)
    
    return sorted(fg5_files)


def get_fg5_files_from_subdirs(session_path):
    """
    Gets all *.fg5 files from north_xx, south_xx folders in the raw session folder (for 'zero' order).
    Structure: {session_path}/raw/north_xx/*.fg5 or {session_path}/raw/south_xx/*.fg5
    
    Args:
        session_path (str): Full path to the session folder (YYYYMMDD)
    
    Returns:
        dict: Dictionary {direction: [list of fg5 files]}
    """
    fg5_by_direction = {}
    raw_path = os.path.join(session_path, 'raw')
    
    if not os.path.exists(raw_path):
        return fg5_by_direction
    
    # Look for north_xx, south_xx folders inside the raw folder
    for folder in os.listdir(raw_path):
        if folder.startswith(('north_', 'south_')):
            folder_path = os.path.join(raw_path, folder)
            if os.path.isdir(folder_path):
                fg5_files = []
                for file in os.listdir(folder_path):
                    if file.endswith('.fg5'):
                        fg5_path = os.path.join(folder_path, file)
                        fg5_files.append(fg5_path)
                
                if fg5_files:
                    fg5_by_direction[folder] = sorted(fg5_files)
    
    return fg5_by_direction


def expand_dataframe_with_fg5_files(df, point_path_col='full_path'):
    """
    Expands DataFrame with new records for each *.fg5 file.
    Supports different structures for 'first' and 'zero' orders:
    - 'first': {point}/absolute/{YYYYMMDD}/raw/*.fg5
    - 'zero': {point}/absolute/{YYYYMMDD}/{north_xx,south_xx}/*.fg5
    
    Args:
        df (pd.DataFrame): Source DataFrame with paths to points
        point_path_col (str): Column name with path to point folder
    
    Returns:
        pd.DataFrame: Expanded DataFrame with *.fg5 file information
    """
    expanded_rows = []
    
    for idx, row in df.iterrows():
        point_path = row[point_path_col]
        order = row.get('order', 'first')
        
        # Get all sessions for this point
        sessions = get_session_folders(point_path)
        
        if not sessions:
            # If no sessions, add the original row with empty values
            new_row = row.copy()
            new_row['session_date'] = None
            new_row['direction'] = None
            new_row['fg5_file'] = None
            expanded_rows.append(new_row)
        else:
            # Process each session
            for session_path in sessions:
                session_date = os.path.basename(session_path)
                
                if order == 'zero':
                    # For 'zero' - look for north_xx, south_xx folders
                    fg5_by_direction = get_fg5_files_from_subdirs(session_path)
                    
                    if not fg5_by_direction:
                        # If no folders with files
                        new_row = row.copy()
                        new_row['session_date'] = session_date
                        new_row['direction'] = None
                        new_row['fg5_file'] = None
                        expanded_rows.append(new_row)
                    else:
                        # For each folder (direction) and each file create a row
                        for direction, fg5_files in fg5_by_direction.items():
                            for fg5_file in fg5_files:
                                new_row = row.copy()
                                new_row['session_date'] = session_date
                                new_row['direction'] = direction
                                new_row['fg5_file'] = fg5_file
                                expanded_rows.append(new_row)
                else:
                    # For 'first' - use the structure with 'raw' folder
                    fg5_files = get_fg5_files(session_path)
                    
                    if not fg5_files:
                        # If no files in session
                        new_row = row.copy()
                        new_row['session_date'] = session_date
                        new_row['direction'] = None
                        new_row['fg5_file'] = None
                        expanded_rows.append(new_row)
                    else:
                        # For each file create a row
                        for fg5_file in fg5_files:
                            new_row = row.copy()
                            new_row['session_date'] = session_date
                            new_row['direction'] = None
                            new_row['fg5_file'] = fg5_file
                            expanded_rows.append(new_row)
    
    return pd.DataFrame(expanded_rows).reset_index(drop=True)

def add_comments(row, comments_text):
    """Add comments to the row based on the order and direction."""
    if row['order'] == 'zero' and pd.notna(row.get('direction')) and row['direction'] is not None:
        # get direction and approach: "north_01" -> ["north", "01"]
        parts = str(row['direction']).split('_')
        if len(parts) == 2:
            direction_part = parts[0]  # north or south
            approach_part = parts[1]   # 01, 02, 03, etc.
            return f"{comments_text}\n\nDirection: {direction_part}\n\nApproach: {approach_part}"
    return comments_text

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
        print(f"[INFO] Filling {len(lines)} lines of text")
        
        # Type each line character by character, handling spaces explicitly
        for i, line in enumerate(lines):
            print(f"[INFO] Line {i}: {line[:50] if len(line) > 50 else line}")
            
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
        
        print("[OK] Text filled successfully")
        return True
    except Exception as e:
        print(f"[FAIL] Error: {e}")
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
    print("[OK] File dialog opened")
    
    # try to find ComboBox Edit control
    edit_controls = file_dialog.child_window(class_name='Edit')
    edit_controls.set_text(project_path)
    print("[OK] Path entered")
    
    # Enter key or click Open/OK button
    time.sleep(1)
    keyboard.send_keys('{ENTER}')
    time.sleep(1)
    print("[OK] File opened")

def info_tab(setup_dialog, row):
    # go to Information tab if it exists
    info_tab = setup_dialog.child_window(title_re='.*Information.*')
    info_tab.click()
    time.sleep(1)
    print("[OK] Transitioned to Information tab")
    
    # fill fields from DataFrame
    print("\n=== Filling Fields ===")
    find_and_fill_edit(setup_dialog, 'Name:', row.station)
    find_and_fill_edit(setup_dialog, 'Code:', row.point)
    find_and_fill_edit(setup_dialog, 'Latitude', row.latitude)
    find_and_fill_edit(setup_dialog, 'Longitude', row.longitude)
    find_and_fill_edit(setup_dialog, 'Elevation', row.elevation)
    find_and_fill_edit(setup_dialog, 'Gradient', row.vgg)
    find_and_fill_edit(setup_dialog, 'Transfer Height', row.transfer_height)
    find_and_fill_edit(setup_dialog, 'Polar X', row.polar_x)
    find_and_fill_edit(setup_dialog, 'Polar Y', row.polar_y)
    
    print("[OK] All fields filled")
    
    # click "Set" button
    time.sleep(0.5)
    set_button = setup_dialog.child_window(title='Set', class_name='Button')
    set_button.click()
    print("[OK] \"Set\" button clicked")
    
    time.sleep(1)

def system_tab(app, setup_dialog, row):
    # Transition to System tab - find tab control and select the desired tab
    system_tab = setup_dialog.child_window(class_name='SysTabControl32')
    # Choose System tab (index 1, as Information - 0)
    system_tab.select(1)  # 1 = System tab
    print("[OK] Transitioned to System tab")
    
    time.sleep(1)
    
    print("\n=== Working with Laser ===")

    # find the Laser button (Group)
    setup_button = setup_dialog.child_window(control_id=1029, class_name='Button')
    setup_button.click()
    print("[OK] Laser Setup button pressed")
        
    time.sleep(1)
    
    laser_setup_dialog = app.window(title_re='.*L Series.*')
    laser_setup_dialog.wait('visible', timeout=5)
    print("[OK] L Series dialog opened")

    time.sleep(1)
    
    # find and fill fields Red Lock and Blue Lock in the Wavelengths group
    print("\n=== Filling Laser Parameters ===")
    
    find_and_fill_edit(laser_setup_dialog, 'Red Lock', row.laser_red)
    find_and_fill_edit(laser_setup_dialog, 'Blue Lock', row.laser_blue)
    
    time.sleep(0.5)
    
    # close L Series dialog (try OK button first, then Close)
    print("\n=== Closing L Series Dialog ===")
    ok_button = laser_setup_dialog.child_window(title='OK', class_name='Button')
    ok_button.click()
        
    time.sleep(2)
        
    # return to Setup dialog and click Advanced button on System tab
    print("\n=== Working with Advanced on System Tab ===")
    advanced_button = setup_dialog.child_window(title='Advanced...', class_name='Button')
    advanced_button.click()
    print("[OK] Advanced button clicked")
            
    time.sleep(2)
            
    advanced_dialog = app.window(title_re='.*Advanced.*')
    advanced_dialog.wait('visible', timeout=5)
    print("[OK] Advanced Settings dialog opened")
    
    time.sleep(1)
                
    # find and fill Clock Frequency field
    print("\n=== Filling Clock Frequency ===")
    find_and_fill_edit(advanced_dialog, 'Clock Frequency', row.frequency)
            
    time.sleep(0.5)
                
    ok_button = advanced_dialog.child_window(title='OK', class_name='Button')
    ok_button.click()
    print("[OK] Advanced Settings dialog closed")
    
    time.sleep(1)

def control_tab(app, setup_dialog, config):
    # go to control tab
    print("\n=== Transitioning to Control Tab ===")
    tab_control = setup_dialog.child_window(class_name='SysTabControl32')
    tab_control.select(3)  # 3 = Control tab (Information=0, System=1, Acquisition=2, Control=3)
    print("[OK] Control tab opened")
    
    time.sleep(1)
        
    # Press the Setup button in the Corrections group
    print("\n=== Opening Corrections Setup ===")
    setup_button = setup_dialog.child_window(control_id=1454, class_name='Button')
    setup_button.click()
    print("[OK] Corrections Setup button pressed")
    
    time.sleep(2)
    
    # Find the Corrections Setup dialog
    corrections_dialog = app.window(title_re='.*Corrections.*')
    corrections_dialog.wait('visible', timeout=5)
    print("[OK] Corrections Setup dialog opened")
    
    time.sleep(1)
    
    # Determine which checkboxes should be checked
    checkboxes_to_check = config['corrections']['checkboxes']
    
    print("\n=== Setting Checkbox States ===")
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
                print(f"  '{checkbox_name}': current state = {is_checked}, needed = {should_be_checked}")
                if is_checked != should_be_checked:
                    checkbox.click()
                    print(f"    [OK] {checkbox_name}")
                    time.sleep(0.3)
            except Exception as e:
                print(f"  [FAIL] {checkbox_name}: {e}")
        else:
            print(f"  [FAIL] {checkbox_name} not found")
    
    print("\n=== Filling Edit Fields ===")
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
        # if index < len(edit_fields):
            edit_field = edit_fields[index][1]
            target_value = correction_values.get(label_text, '')
            if target_value:
                edit_field.set_text(target_value)
                print(f"[OK] {label_text}: {target_value}")
            time.sleep(0.2)
        # else:
            # print(f"[FAIL] Edit field index {index} not found (available {len(edit_fields)})")
    
    # Close the dialog
    print("\n=== Closing Corrections ===")
    ok_button = corrections_dialog.child_window(title='OK', class_name='Button')
    ok_button.click()
    print("[OK] Corrections dialog closed")
    
    time.sleep(1)
        
        
    # Uncheck System Response Compensation if set
    print("\n=== Checking System Response Compensation ===")
    sys_response_checkbox = setup_dialog.child_window(title='System Response Compensation', class_name='Button')
    if sys_response_checkbox.is_checked():
        sys_response_checkbox.click()
        print("[OK] System Response Compensation unchecked")
        time.sleep(0.3)
    else:
        print("[OK] System Response Compensation already unchecked")
    
    # Press the Setup button in the Uncertainty group
    print("\n=== Opening Uncertainties ===")
    setup_dialog.child_window(control_id=1241, class_name='Button').click()
    print("[OK] Uncertainties Setup button pressed")
    
    time.sleep(2)
    
    uncertainties_dialog = app.window(title_re='.*Uncertainties.*')
    uncertainties_dialog.wait('visible', timeout=5)
    print("[OK] Uncertainties dialog opened")
    
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
    print("\n=== Filling Uncertainties ===")
    uncertainties_values = config['uncertainties']
    for label_text, target_value in uncertainties_values.items():
        ctrl_id = label_to_ctrl_id.get(label_text)
        if ctrl_id:
            edit_field = uncertainties_dialog.child_window(control_id=ctrl_id, class_name='Edit')
            edit_field.set_text(target_value)
            print(f"[OK] {label_text}: {target_value}")
            time.sleep(0.2)
        else:
            print(f"[FAIL] Unknown label: '{label_text}'")
    
    # Press Update and close the dialog
    print("\n=== Closing Uncertainties dialog ===")
    time.sleep(1)
    
    uncertainties_dialog.child_window(control_id=1382, class_name='Button').click()
    print("[OK] 'Update' button pressed")
    time.sleep(1)
    
    uncertainties_dialog.child_window(control_id=1, class_name='Button').click()
    print("[OK] 'Uncertainties' dialog closed")
    time.sleep(2)

def comments_tab(setup_dialog, row, config):
    # Transition to Comments tab
    print("\n=== Transitioning to Comments Tab ===")
    time.sleep(1)
    setup_dialog.set_focus()
    time.sleep(0.5)
    tab_control = setup_dialog.child_window(class_name='SysTabControl32')
    tab_control.select(4)  # 4 = Comments tab
    print("[OK] Comments tab opened")
    time.sleep(1)
            
    # Fill fields on the Comments tab
    print("\n=== Filling Comments ===")
    find_and_fill_edit(setup_dialog, 'Company/Institution:', config['comments_tab']['company_institution'])
    today = datetime.now().strftime("%Y-%m-%d")
    comments_with_date = f"=== Reprocessing comments === \n\nDate: {today}\n\n{row.comments}"
    comments_edit = setup_dialog.child_window(control_id=1054, class_name='Edit')
    fill_multiline_field(comments_edit, comments_with_date, clear=True)
    print("[OK] Comments filled")
 
 
def setup_dialog(app, main, row, config):

    # open setup dialog
    time.sleep(1)
    main.menu_select('Process->Setup')

    print('[OK] Setup Dialog should be opened now')
    
    # find setup dialog
    setup_dialog = app.window(title_re='.*Setup.*')
    setup_dialog.wait('visible', timeout=3)
    
    # info_tab(setup_dialog, row)
   
    # system_tab(app, setup_dialog, row)  

    # config['uncertainties']['Grad. Uncert. (µGal/cm):'] = row.vgg_ste
    # control_tab(app, setup_dialog, config) 

    comments_tab(setup_dialog, row, config)
   
    # Close Setup dialog by clicking OK button (Russian title 'ОК')
    time.sleep(0.5)
    ok_button = setup_dialog.child_window(control_id=1, class_name='Button')
    ok_button.click()
    print("[OK] Setup dialog closed")

def run_process(app, main):
    # Start processing: Process -> Go
    print("\n=== Starting Processing ===")
    main.menu_select('Process->Go')
    print("[OK] Processing started")
    
    # Check for Override Dialog and click Yes if it appears (appears immediately after Go)
    print("\n=== Checking Override Dialog ===")
    try:
        override_dialog = app.window(title_re='.*Override.*')
        override_dialog.wait('visible', timeout=3)
        print("[OK] Override dialog appeared")
        yes_button = override_dialog.child_window(control_id=1, class_name='Button')
        yes_button.click()
        print("[OK] Yes button clicked")
        time.sleep(2)
    except:
        print("[INFO] No Override dialog - continuing")

def save_project(main):
    # Save project
    print("\n=== Saving ===")
    time.sleep(1)
    main.menu_select('Project->Save')
    print("[OK] Saved")

def close_project(main):

    time.sleep(2)
    print("\n=== Closing ===")
    main.menu_select('Project->Close')
    print("[OK] Closed")
    time.sleep(2)

def close_app(main):
    # Close the application
    print("\n=== Shutting Down ===")
    time.sleep(1)
    main.close()
    print("[OK] Application closed")
    print("\n✓ All projects processed!")


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
        print(f"\n=== Open project ===")
        print(f"[INFO] Path: {project_path}")
        print(f"[INFO] Order: {order}")
        print(f"[INFO] Station: {station_id}")

        open_project(app, main, project_path)
       
        time.sleep(1)

        setup_dialog(app, main, row, config)
       
        time.sleep(2)
        
        # run_process(app, main)  
        # Wait for processing to complete with timeout based on config
        print("\n=== Waiting for Processing to Complete ===")
        
        # Use timeout from config or default to 2 minutes
        # max_wait_time = config.get('processing', {}).get('timeout_seconds', 120)
        # print(f"[INFO] Waiting up to {max_wait_time} seconds for processing to complete...")
        
        # time.sleep(max_wait_time)
        # print(f"[OK] Processing timeout reached, proceeding with save and close")
        
        # save_project(main)

        # close_project(main)
        
    close_app(main)