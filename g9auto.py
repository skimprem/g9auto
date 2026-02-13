import os
import json
import pandas as pd
from pywinauto.application import Application
import time
from functions import get_full_path, get_session_folders, get_fg5_files, expand_dataframe_with_fg5_files
from functions import add_comments, find_and_fill_edit

# get config
with open('config.json', 'r', encoding='utf-8') as f:
    config = json.load(f)

# get paths
info_path = config['paths']['info_path']
data_path = config['paths']['data_path']

comments_file = os.path.join(info_path, config['paths']['comments_file'])
comments_text = open(comments_file, 'r', encoding='utf-8').read()

first_path = os.path.join(info_path, config['paths']['first_absolute_file'])
zero_path = os.path.join(info_path, config['paths']['zero_absolute_file'])

df_first = pd.read_csv(first_path, sep=';')
df_first['order'] = 'first'
df_zero = pd.read_csv(zero_path, sep=';')
df_zero['order'] = 'zero'

df = pd.concat([df_first, df_zero], ignore_index=True)

df['full_path'] = df.apply(lambda row: get_full_path(data_path, row['order'], row['station'], row['point']), axis=1)

# search *.fg5 and expand dataframe
df_ex = expand_dataframe_with_fg5_files(df, 'full_path')

# add comments
df_ex['comments'] = df_ex.apply(lambda row: add_comments(row, comments_text), axis=1)

output_file = os.path.join(config['paths']['output_dir'], 'expanded_data.json')
os.makedirs(config['paths']['output_dir'], exist_ok=True)
df_ex.to_json(output_file, orient='records')

# get specific station
df_ex = df_ex[df_ex['station'] == config['filter']['station']]

app = Application(backend = 'win32').start(config['paths']['g9_exe'])

time.sleep(1)

# find main window
main = app.window(title_re='.*Micro-g.*')
main.wait('visible', timeout=1)

time.sleep(1)
main.menu_select('Project->&Open Project...')

time.sleep(1)

for row in df_ex.itertuples():

    project_path = row.fg5_file
    order = row.order
    station_id = row.station
    
    # find dialog for opening file by class (standard dialog class)
    file_dialog = app.window(class_name='#32770')
    file_dialog.wait('visible', timeout=1)
    
    print('Dialog for opening file found')
    
    # try to find ComboBox Edit control
    edit_controls = file_dialog.child_window(class_name='Edit')
    edit_controls.set_text(project_path)
    
    print('Path entered')
    
    # Enter key or click Open/OK button
    time.sleep(1)

    import pywinauto.keyboard as keyboard
    keyboard.send_keys('{ENTER}')
    
    time.sleep(1)
    print('The project should be opened now')
    
    # open setup dialog
    time.sleep(1)
    main.menu_select('Process->Setup')
    
    time.sleep(1)
    print('Setup Dialog should be opened now')
    
    # find setup dialog
    setup_dialog = app.window(title_re='.*Setup.*')
    setup_dialog.wait('visible', timeout=3)
    
    # go to Information tab if it exists
    info_tab = setup_dialog.child_window(title_re='.*Information.*')
    info_tab.click()
    time.sleep(1)
    print('Transition to information tab')
    
    # fill fields from DataFrame
    print('\n=== Fill Fields from DataFrame ===')
    find_and_fill_edit(setup_dialog, 'Name:', row.station)
    find_and_fill_edit(setup_dialog, 'Code:', row.point)
    find_and_fill_edit(setup_dialog, 'Latitude', row.latitude)
    find_and_fill_edit(setup_dialog, 'Longitude', row.longitude)
    find_and_fill_edit(setup_dialog, 'Elevation', row.elevation)
    find_and_fill_edit(setup_dialog, 'Gradient', row.vgg)
    find_and_fill_edit(setup_dialog, 'Transfer Height', row.transfer_height)
    find_and_fill_edit(setup_dialog, 'Polar X', row.polar_x)
    find_and_fill_edit(setup_dialog, 'Polar Y', row.polar_y)
    
    print('[OK] All fields filled successfully')
    
    # click "Set" button
    time.sleep(0.5)
    set_button = setup_dialog.child_window(title='Set', class_name='Button')
    set_button.click()
    print('[OK] "Set" button clicked successfully')
    
    time.sleep(1)
    
    # Transition to System tab - find tab control and select the desired tab
    tab_control = setup_dialog.child_window(class_name='SysTabControl32')
    # Choose System tab (index 1, as Information - 0)
    tab_control.select(1)  # 1 = System tab
    print('[OK] Transition to "System" tab')
    
    time.sleep(1)
    
    print('\n=== work with Laser ===')

    # find the Laser button (Group)
    setup_button = setup_dialog.child_window(control_id=1029, class_name='Button')
    setup_button.click()
    print('[OK] "Setup" button pressed in Laser group')
        
    time.sleep(1)
    
    laser_setup_dialog = app.window(title_re='.*L Series.*')
    laser_setup_dialog.wait('visible', timeout=5)
    print('[OK] "L Series" dialog opened')

    time.sleep(1)
    
    # find and fill fields Red Lock and Blue Lock in the Wavelengths group
    print("\n=== Filling Laser Parameters ===")
    
    find_and_fill_edit(laser_setup_dialog, 'Red Lock', row.laser_red)
    find_and_fill_edit(laser_setup_dialog, 'Blue Lock', row.laser_blue)
    
    time.sleep(0.5)
    
    # close L Series dialog (try OK button first, then Close)
    print('\n=== L Series dialog close ===')
    ok_button = laser_setup_dialog.child_window(title='OK', class_name='Button')
    ok_button.click()
        
    time.sleep(2)
        
    # return to Setup dialog and click Advanced button on System tab
    print('\n=== Work with Advanced on System tab ===')
        
    advanced_button = setup_dialog.child_window(title='Advanced...', class_name='Button')
    advanced_button.click()
    print("[OK] 'Advanced...' button clicked in Setup")
            
    time.sleep(2)
            
    advanced_dialog = app.window(title_re='.*Advanced.*')
    advanced_dialog.wait('visible', timeout=5)
    print("[OK] 'Advanced Settings' dialog opened")
    
    time.sleep(1)
                
    # find and fill Clock Frequency field
    print('\n=== Filling Clock Frequency ===')
    find_and_fill_edit(advanced_dialog, 'Clock Frequency', row.frequency)
            
    time.sleep(0.5)
                
    ok_button = advanced_dialog.child_window(title='OK', class_name='Button')
    ok_button.click()
    print('[OK] "Advanced Settings" dialog is closed')
    
    time.sleep(1)
        
    # go to control tab
    print('\n=== Transition to Control tab ===')
    tab_control = setup_dialog.child_window(class_name='SysTabControl32')
    tab_control.select(3)  # 3 = Control tab (Information=0, System=1, Acquisition=2, Control=3)
    print("[OK] Transition to 'Control' tab")
    
    time.sleep(1)
        
    # Нажимаем кнопку Setup в группе Corrections
    print("\n=== Открытие диалога Corrections Setup ===")
    setup_button = setup_dialog.child_window(control_id=1454, class_name='Button')
    setup_button.click()
    print("[OK] Нажата кнопка Setup в группе Corrections")
    
    time.sleep(2)
    
    # Ищем диалог Corrections Setup
    corrections_dialog = app.window(title_re='.*Corrections.*')
    corrections_dialog.wait('visible', timeout=5)
    print("[OK] Диалог 'Corrections Setup' открыт")
    
    time.sleep(1)
    
    # Определяем какие checkboxы должны быть активны
    checkboxes_to_check = config['corrections']['checkboxes']
    
    print("\n=== Установка галочек CheckBox ===")
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
            # Проверяем текущее состояние checkbox
            try:
                is_checked = checkbox.is_checked()
                print(f"  '{checkbox_name}': текущее состояние = {is_checked}, нужно = {should_be_checked}")
                
                # Если состояние нужно изменить
                if is_checked != should_be_checked:
                    checkbox.click()
                    print(f"    [OK] Кликнули '{checkbox_name}'")
                    time.sleep(0.3)
            except Exception as e:
                print(f"  [FAIL] Ошибка при работе с '{checkbox_name}': {e}")
        else:
            print(f"  [FAIL] CheckBox '{checkbox_name}' не найден")
    
    print("\n=== Заполнение Edit полей ===")
    # Заполняем Edit поля значениями из конфика
    correction_values = config['corrections']['values']
    
    # Собираем все Edit поля и заполняем их
    edit_fields = []
    for control in all_controls:
        try:
            if control.class_name() == 'Edit':
                rect = control.rectangle()
                edit_fields.append((rect.top, control))
        except:
            pass
    
    # Сортируем по вертикальной позиции (сверху вниз)
    edit_fields.sort(key=lambda x: x[0])
    
    # Заполняем Edit поля в порядке:
    # 1. Baro. Fact (первое Edit)
    # 2. Self Attraction Correction (второе Edit)
    # 3. Diffraction Correction (третье Edit)
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
            print(f"[OK] '{label_text}' заполнено: {target_value}")
            time.sleep(0.2)
        # else:
            # print(f"[FAIL] Индекс Edit поля {index} не найден (доступно {len(edit_fields)})")
    
    # Закрываем диалог
    print("\n=== Закрытие диалога Corrections ===")
    # try:
    ok_button = corrections_dialog.child_window(title='OK', class_name='Button')
    ok_button.click()
    print("[OK] Диалог 'Corrections Setup' закрыт (OK)")
    
    time.sleep(1)
        
        
    # Снимаем галочку System Response Compensation (если стоит)
    print("\n=== Проверка System Response Compensation ===")
    sys_response_checkbox = setup_dialog.child_window(title='System Response Compensation', class_name='Button')
    if sys_response_checkbox.is_checked():
        sys_response_checkbox.click()
        print("[OK] Убрали галочку 'System Response Compensation'")
        time.sleep(0.3)
    else:
        print("[OK] 'System Response Compensation' уже снята")
    
    # Нажимаем кнопку Setup в группе Uncertainty
    print("\n=== Открытие диалога Uncertainties ===")
    setup_dialog.child_window(control_id=1241, class_name='Button').click()
    print("[OK] Нажата кнопка 'Setup' в группе Uncertainty")
    
    time.sleep(2)
    
    uncertainties_dialog = app.window(title_re='.*Uncertainties.*')
    uncertainties_dialog.wait('visible', timeout=5)
    print("[OK] Диалог 'Uncertainties' открыт")
    
    time.sleep(1)
    
    # Маппинг: label из конфига -> control_id Edit поля
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
    
    # Заполняем поля Uncertainties согласно конфигу
    print("\n=== Заполнение полей Uncertainties ===")
    uncertainties_values = config['uncertainties']
    
    for label_text, target_value in uncertainties_values.items():
        ctrl_id = label_to_ctrl_id.get(label_text)
        if ctrl_id:
            edit_field = uncertainties_dialog.child_window(control_id=ctrl_id, class_name='Edit')
            edit_field.set_text(target_value)
            print(f"[OK] '{label_text}' заполнено: {target_value}")
            time.sleep(0.2)
        else:
            print(f"[FAIL] Неизвестный label: '{label_text}'")
    
    # Нажимаем Update и закрываем диалог
    print("\n=== Закрытие диалога Uncertainties ===")
    time.sleep(1)
    
    uncertainties_dialog.child_window(control_id=1382, class_name='Button').click()
    print("[OK] Нажата кнопка 'Update'")
    time.sleep(1)
    
    uncertainties_dialog.child_window(control_id=1, class_name='Button').click()
    print("[OK] Диалог 'Uncertainties' закрыт")
    time.sleep(2)
                
    # Переходим на вкладку Comments
    print("\n=== Переход на вкладку Comments ===")

    # Даем установке время убедиться, что диалог закрыт
    time.sleep(1)

    # Убеждаемся, что Setup диалог все еще активен
    setup_dialog.set_focus()
    time.sleep(0.5)

    tab_control = setup_dialog.child_window(class_name='SysTabControl32')
    tab_control.select(4)  # 4 = Comments tab
    print("[OK] Переход на вкладку 'Comments'")

    time.sleep(1)
            
    # Заполняем поля на вкладке Comments
    print("\n=== Заполнение полей Comments ===")

    all_controls = list(setup_dialog.children())
    
    # Заполняем Company/Institution
    company_static = None
    for control in all_controls:
        if control.class_name() == 'Static' and 'Company/Institution' in control.window_text():
            company_static = control
            break

        if company_static:
            company_rect = company_static.rectangle()
        
            # Ищем Edit справа от Company/Institution
            candidates = []
            for control in all_controls:
                try:
                    if control.class_name() == 'Edit':
                        child_rect = control.rectangle()
                        # Проверяем, находится ли Edit справа и на одной строке со Static
                        same_row = abs(child_rect.top - company_rect.top) < 20
                        is_to_the_right = child_rect.left > company_rect.right
                    
                        if same_row and is_to_the_right:
                            distance = child_rect.left - company_rect.right
                            candidates.append((distance, control))
                except:
                    pass
        
            if candidates:
                candidates.sort(key=lambda x: x[0])
                company_edit = candidates[0][1]
            
                # Очищаем поле и вводим новое значение
                company_edit.send_keystrokes('^a')  # Select all
                time.sleep(0.1)
                company_edit.set_text(config['comments_tab']['company_institution'])
                time.sleep(0.5)
            
                # Отправляем фокус из поля
                company_edit.send_keystrokes('{TAB}')
                time.sleep(0.3)
            
                print(f"[OK] 'Company/Institution' заполнено: {config['comments_tab']['company_institution']}")
   
    #     # Заполняем большое поле Comments
    #     try:
    #         comments_text = row.get('comments', '')
    #         if comments_text:
    #             # Ищем большое Edit поле для комментариев (height > 150)
    #             large_edits = []
    #             for control in all_controls:
    #                 try:
    #                     if control.class_name() == 'Edit':
    #                         rect = control.rectangle()
    #                         height = rect.bottom - rect.top
    #                         width = rect.right - rect.left
    #                         # Ищем поле с большой высотой
    #                         if height > 150:
    #                             large_edits.append((control, rect, height, width))
    #                 except:
    #                     pass
            
    #             if large_edits:
    #                 # Берем первое крупное поле
    #                 large_edits.sort(key=lambda x: x[2], reverse=True)
    #                 comments_edit = large_edits[0][0]
                
    #                 # Очищаем поле и вводим новое значение
    #                 comments_edit.send_keystrokes('^a')  # Select all
    #                 time.sleep(0.1)
                
    #                 # Разделяем текст по переводам строк и вводим с Ctrl+Enter между ними
    #                 lines = comments_text.split('\n')
    #                 comments_edit.set_text(lines[0])  # Первая строка
    #                 time.sleep(0.1)
                
    #                 # Остальные строки вводим после Ctrl+Enter
    #                 for line in lines[1:]:
    #                     comments_edit.send_keystrokes('^{ENTER}')  # Ctrl+Enter для новой строки
    #                     time.sleep(0.2)
    #                     comments_edit.type_keys(line)  # Вводим текст строки
    #                     time.sleep(0.1)
                
    #                 time.sleep(0.5)
                
    #                 # Отправляем фокус из поля
    #                 comments_edit.send_keystrokes('{TAB}')
    #                 time.sleep(0.3)
                
    #                 print(f"[OK] Поле Comments заполнено ({len(comments_text)} символов, {len(lines)} строк)")
    #             else:
    #                 print("[INFO] Большое поле для Comments не найдено")
    #         else:
    #             print("[INFO] comments_text пуста")
    #     except Exception as e:
    #         print(f"[FAIL] Ошибка при заполнении Comments: {e}")
                
    # time.sleep(1)
