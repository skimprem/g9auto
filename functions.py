import os
import pandas as pd


def get_full_path(common_path, order, station_id, point_id):
    """
    Формирует и проверяет существование полного пути к проектам точки.
    Поддерживает разные форматы точек: 079, 79, 0079, 486, 8406 и т.д.
    
    Args:
        common_path (str): Базовый путь до проектов
        order (str): Порядок (first/zero)
        station_id (str): ID станции (3-4 буквы)
        point_id (str|int): ID точки (4 буквы или число от 1-9999)
    
    Returns:
        str: Полный путь к точке, если он существует
        
    Raises:
        ValueError: Если путь не существует
    """
    
    point_id_str = str(point_id).strip()
    station_path = os.path.join(common_path, f'{order}_order', f'{station_id}')
    
    # Если буквенное обозначение - ищем папку с точным совпадением или в верхнем регистре
    if not point_id_str.isdigit():
        # Пробуем разные варианты для букв
        variants = [point_id_str, point_id_str.upper(), point_id_str.lower()]
        for variant in variants:
            full_path = os.path.join(station_path, variant)
            if os.path.exists(full_path):
                return full_path
    else:
        # Для числовых ID генерируем варианты и ищем существующие папки
        # Преобразуем в число для работы
        point_num = int(point_id_str)
        
        # Генерируем возможные варианты названий папок
        variants = []
        
        # Исходный строковый формат
        variants.append(point_id_str)
        
        # С нулями впереди до 3, 4, 5 символов
        for width in range(3, 6):
            padded = str(point_num).zfill(width)
            if padded not in variants:
                variants.append(padded)
        
        # Без нулей впереди (только цифры)
        stripped = str(point_num).lstrip('0') or '0'
        if stripped not in variants:
            variants.append(stripped)
        
        # Пробуем каждый вариант
        for variant in variants:
            full_path = os.path.join(station_path, variant)
            if os.path.exists(full_path):
                return full_path
    
    # Если ничего не найдено, показываем ошибку
    raise ValueError(f"Путь не существует. Станция: {station_id}, точка: {point_id}")


def get_session_folders(point_path):
    """
    Получает все папки сессий (YYYYMMDD) в папке absolute точки.
    
    Args:
        point_path (str): Полный путь к папке точки
    
    Returns:
        list: Список путей к папкам сессий (YYYYMMDD)
    """
    absolute_path = os.path.join(point_path, 'absolute')
    
    if not os.path.exists(absolute_path):
        return []
    
    sessions = []
    for folder in os.listdir(absolute_path):
        folder_path = os.path.join(absolute_path, folder)
        # Проверяем, что это папка и название соответствует формату YYYYMMDD (8 цифр)
        if os.path.isdir(folder_path) and folder.isdigit() and len(folder) == 8:
            sessions.append(folder_path)
    
    return sorted(sessions)


def get_fg5_files(session_path):
    """
    Получает все файлы *.fg5 из папки raw сессии.
    
    Args:
        session_path (str): Полный путь к папке сессии (YYYYMMDD)
    
    Returns:
        list: Список путей к файлам *.fg5
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
    Получает все файлы *.fg5 из папок north_xx, south_xx в папке raw сессии (для 'zero' порядка).
    Структура: {session_path}/raw/north_xx/*.fg5 или {session_path}/raw/south_xx/*.fg5
    
    Args:
        session_path (str): Полный путь к папке сессии (YYYYMMDD)
    
    Returns:
        dict: Словарь {direction: [list of fg5 files]}
    """
    fg5_by_direction = {}
    raw_path = os.path.join(session_path, 'raw')
    
    if not os.path.exists(raw_path):
        return fg5_by_direction
    
    # Ищем папки north_xx, south_xx внутри папки raw
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
    Расширяет DataFrame новыми записями для каждого файла *.fg5.
    Поддерживает разные структуры для 'first' и 'zero' порядков:
    - 'first': {point}/absolute/{YYYYMMDD}/raw/*.fg5
    - 'zero': {point}/absolute/{YYYYMMDD}/{north_xx,south_xx}/*.fg5
    
    Args:
        df (pd.DataFrame): Исходный DataFrame с путями к точкам
        point_path_col (str): Название колонки с путем к папке точки
    
    Returns:
        pd.DataFrame: Расширенный DataFrame с информацией о файлах *.fg5
    """
    expanded_rows = []
    
    for idx, row in df.iterrows():
        point_path = row[point_path_col]
        order = row.get('order', 'first')
        
        # Получаем все сессии для этой точки
        sessions = get_session_folders(point_path)
        
        if not sessions:
            # Если нет сессий, добавляем исходную строку с пустыми значениями
            new_row = row.copy()
            new_row['session_date'] = None
            new_row['direction'] = None
            new_row['fg5_file'] = None
            expanded_rows.append(new_row)
        else:
            # Обрабатываем каждую сессию
            for session_path in sessions:
                session_date = os.path.basename(session_path)
                
                if order == 'zero':
                    # Для 'zero' - ищем папки north_xx, south_xx
                    fg5_by_direction = get_fg5_files_from_subdirs(session_path)
                    
                    if not fg5_by_direction:
                        # Если нет папок с файлами
                        new_row = row.copy()
                        new_row['session_date'] = session_date
                        new_row['direction'] = None
                        new_row['fg5_file'] = None
                        expanded_rows.append(new_row)
                    else:
                        # Для каждой папки (direction) и каждого файла создаем строку
                        for direction, fg5_files in fg5_by_direction.items():
                            for fg5_file in fg5_files:
                                new_row = row.copy()
                                new_row['session_date'] = session_date
                                new_row['direction'] = direction
                                new_row['fg5_file'] = fg5_file
                                expanded_rows.append(new_row)
                else:
                    # Для 'first' - используем структуру с папкой 'raw'
                    fg5_files = get_fg5_files(session_path)
                    
                    if not fg5_files:
                        # Если нет файлов в сессии
                        new_row = row.copy()
                        new_row['session_date'] = session_date
                        new_row['direction'] = None
                        new_row['fg5_file'] = None
                        expanded_rows.append(new_row)
                    else:
                        # Для каждого файла создаем строку
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
