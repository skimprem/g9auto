import os
import pandas as pd


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
