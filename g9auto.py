import os
import json
import pandas as pd
from pywinauto.application import Application
import time
from functions import get_full_path, get_session_folders, get_fg5_files, expand_dataframe_with_fg5_files
from functions import add_comments

# Загружаем конфиг из JSON файла
with open('config.json', 'r', encoding='utf-8') as f:
    config = json.load(f)

# Извлекаем пути из конфига
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

# Расширяем DataFrame информацией о файлах *.fg5
df_ex = expand_dataframe_with_fg5_files(df, 'full_path')

df_ex['comments'] = df_ex.apply(lambda row: add_comments(row, comments_text), axis=1)

output_file = os.path.join(config['paths']['output_dir'], 'expanded_data.json')
os.makedirs(config['paths']['output_dir'], exist_ok=True)
df_ex.to_json(output_file, orient='records')

df_ex = df_ex[df_ex['station'] == config['filter']['station']]

app = Application(backend = 'win32').start(config['paths']['g9_exe'])

time.sleep(2)

# Ищем главное окно приложения по заголовку
main = app.window(title_re='.*Micro-g.*')
main.wait('visible', timeout=5)

time.sleep(1)
main.menu_select('Project->&Open Project...')

time.sleep(1)

for index, row in df_ex.iterrows():

    project_path = row['fg5_file']
    order = row['order']
    station_id = row['station']
    
    try:
        # Находим диалог открытия файла по классу (стандартный класс диалога)
        file_dialog = app.window(class_name='#32770')
        file_dialog.wait('visible', timeout=3)
        
        print("Диалог открытия найден")
        
        # Попробуем найти Edit контрол для ввода пути (ComboBox Edit)
        edit_controls = file_dialog.child_window(class_name='Edit')
        edit_controls.set_text(project_path)
        
        print("Путь введен")
        
        # Нажимаем кнопку открытия
        time.sleep(1)
        try:
            # Ищем кнопку Open
            open_button = file_dialog.child_window(title='Open', class_name='Button')
            open_button.click()
        except:
            try:
                # Ищем кнопку OK
                ok_button = file_dialog.child_window(title='OK', class_name='Button')
                ok_button.click()
            except:
                # Альтернативный способ - используем клавиатуру
                import pywinauto.keyboard as keyboard
                keyboard.send_keys('{ENTER}')
        
        time.sleep(5)
        print("Проект открыт успешно")
        
        # Открываем диалог Setup
        time.sleep(2)
        main.menu_select('Process->Setup')
        
        time.sleep(3)
        print("Диалог Setup открыт")
        
        # Находим диалог Setup
        setup_dialog = app.window(title_re='.*Setup.*')
        setup_dialog.wait('visible', timeout=3)
        
        # Переходим на вкладку Information (если есть вкладки)
        try:
            info_tab = setup_dialog.child_window(title_re='.*Information.*')
            info_tab.click()
            time.sleep(1)
            print("Переход на вкладку Information")
        except:
            print("Вкладка Information не найдена или не требуется")
        
        # Функция для поиска и заполнения Edit элемента
        def find_and_fill_edit(dialog, label_text, value):
            """Находит Static элемент с label_text и заполняет ближайший Edit элемент справа"""
            try:
                # Находим Static элемент с нужным лейблом
                static_elem = dialog.child_window(title_re=f'.*{label_text}.*', class_name='Static')
                static_rect = static_elem.rectangle()
                
                # Ищем Edit элементы и находим ближайший справа от Static
                candidates = []
                
                # Получаем все Edit элементы в диалоге
                all_children = list(dialog.children())
                
                for child in all_children:
                    try:
                        if child.class_name() == 'Edit':
                            child_rect = child.rectangle()
                            
                            # Проверяем, находится ли Edit справа и на одной строке со Static
                            same_row = abs(child_rect.top - static_rect.top) < 12
                            is_to_the_right = child_rect.left > static_rect.right
                            
                            if same_row and is_to_the_right:
                                distance = child_rect.left - static_rect.right
                                candidates.append((distance, child))
                    except:
                        pass
                
                if candidates:
                    # Выбираем кандидата с наименьшим расстоянием
                    candidates.sort(key=lambda x: x[0])
                    closest_edit = candidates[0][1]
                    
                    closest_edit.set_text(str(value))
                    return True
                else:
                    return False
                    
            except Exception as e:
                return False
        
        # Заполняем поля из DataFrame
        print("\n=== Заполнение полей из DataFrame ===")
        find_and_fill_edit(setup_dialog, 'Name:', row.get('station', ''))
        find_and_fill_edit(setup_dialog, 'Code:', row.get('point', ''))
        find_and_fill_edit(setup_dialog, 'Latitude', row.get('latitude', ''))
        find_and_fill_edit(setup_dialog, 'Longitude', row.get('longitude', ''))
        find_and_fill_edit(setup_dialog, 'Elevation', row.get('elevation', ''))
        find_and_fill_edit(setup_dialog, 'Gradient', row.get('vgg', ''))
        find_and_fill_edit(setup_dialog, 'Transfer Height', row.get('transfer_height', ''))
        find_and_fill_edit(setup_dialog, 'Polar X', row.get('polar_x', ''))
        find_and_fill_edit(setup_dialog, 'Polar Y', row.get('polar_y', ''))
        
        print("[OK] Все поля заполнены успешно")
        
        # Нажимаем кнопку "Set"
        time.sleep(0.5)
        set_button = setup_dialog.child_window(title='Set', class_name='Button')
        set_button.click()
        print("[OK] Нажата кнопка 'Set'")
        
        time.sleep(1)
        
        # Переходим на вкладку System - ищем контроль вкладок и выбираем нужную
        try:
            tab_control = setup_dialog.child_window(class_name='SysTabControl32')
            # Выбираем вкладку System (индекс 1, так как Information - 0)
            tab_control.select(1)  # 1 = System tab
            print("[OK] Переход на вкладку 'System'")
        except Exception as e:
            print(f"[FAIL] Ошибка при переходе на вкладку System: {e}")
        
        time.sleep(1)
        
        # В группе Laser нажимаем кнопку Setup
        try:
            print("\n=== Работа с Laser ===")
            
            # Находим кнопку Laser (Group)
            laser_button = setup_dialog.child_window(title='Laser', class_name='Button')
            laser_rect = laser_button.rectangle()
            print(f"Группа Laser найдена в позиции: top={laser_rect.top}, left={laser_rect.left}, right={laser_rect.right}, bottom={laser_rect.bottom}")
            
            # Ищем ComboBox Type в группе Laser
            print("\n=== Выбор L Series ===")
            all_children = list(setup_dialog.children())
            type_combo = None
            
            for child in all_children:
                try:
                    if child.class_name() == 'ComboBox':
                        child_rect = child.rectangle()
                        # Проверяем, находится ли ComboBox внутри группы Laser
                        if (child_rect.top > laser_rect.top and 
                            child_rect.bottom < laser_rect.bottom and
                            child_rect.left > laser_rect.left and 
                            child_rect.left < laser_rect.right):
                            text = child.window_text()
                            print(f"  Найден ComboBox в группе Laser: '{text}'")
                            type_combo = child
                            break
                except:
                    pass
            
            # Выбираем L Series в ComboBox Type
            if type_combo:
                type_combo.select(0)
                print(f"  [OK] Выбран L Series в ComboBox Type")
                time.sleep(0.5)
            
            # Ищем первую активную кнопку Setup в диапазоне группы Laser
            print("\n=== Поиск активной кнопки Setup ===")
            setup_button = None
            
            for child in all_children:
                try:
                    if child.class_name() == 'Button':
                        title = child.window_text()
                        if 'Setup' in title and child.is_enabled():
                            child_rect = child.rectangle()
                            # Проверяем, находится в диапазоне Laser по Y
                            if laser_rect.top < child_rect.top < laser_rect.bottom:
                                print(f"  [OK] Найдена активная кнопка '{title}' в группе Laser")
                                setup_button = child
                                break
                except:
                    pass
            
            if not setup_button:
                print("[FAIL] Не найдена активная кнопка Setup в диапазоне Laser")
                raise Exception("Setup button not found")
            
            setup_button.click()
            print("[OK] Нажата кнопка 'Setup' в группе Laser")
            
            time.sleep(2)
            
            # Открывается диалог L Series Setup
            try:
                laser_setup_dialog = app.window(title_re='.*L Series.*')
                laser_setup_dialog.wait('visible', timeout=5)
                print("[OK] Диалог 'L Series' открыт")
            except Exception as e:
                print(f"[FAIL] Диалог 'L Series' не открылся: {e}")
                raise
            
            time.sleep(1)
            
            # Находим и заполняем поля Red Lock и Blue Lock в группе Wavelengths
            print("\n=== Заполнение параметров Laser ===")
            red_lock_value = row.get('laser_red', '')
            blue_lock_value = row.get('laser_blue', '')
            
            find_and_fill_edit(laser_setup_dialog, 'Red Lock', red_lock_value)
            print(f"[OK] 'Red Lock' заполнено: {red_lock_value}")
            
            find_and_fill_edit(laser_setup_dialog, 'Blue Lock', blue_lock_value)
            print(f"[OK] 'Blue Lock' заполнено: {blue_lock_value}")
            
            time.sleep(0.5)
            
            # Проверяем, что значения вводились правильно
            print("\n=== Проверка заполнения ===")
            try:
                red_static = laser_setup_dialog.child_window(title_re='.*Red Lock.*', class_name='Static')
                red_rect = red_static.rectangle()
                
                for child in laser_setup_dialog.children():
                    if child.class_name() == 'Edit':
                        child_rect = child.rectangle()
                        if abs(child_rect.top - red_rect.top) < 12 and child_rect.left > red_rect.right:
                            actual_red = child.window_text()
                            print(f"  Red Lock текущее значение: {actual_red}")
                            break
            except Exception as e:
                print(f"  ⚠ Не удалось проверить Red Lock: {e}")
            
            try:
                blue_static = laser_setup_dialog.child_window(title_re='.*Blue Lock.*', class_name='Static')
                blue_rect = blue_static.rectangle()
                
                for child in laser_setup_dialog.children():
                    if child.class_name() == 'Edit':
                        child_rect = child.rectangle()
                        if abs(child_rect.top - blue_rect.top) < 12 and child_rect.left > blue_rect.right:
                            actual_blue = child.window_text()
                            print(f"  Blue Lock текущее значение: {actual_blue}")
                            break
            except Exception as e:
                print(f"  ⚠ Не удалось проверить Blue Lock: {e}")
            
            time.sleep(1)
            
            # Закрываем диалог L Series Setup (нажимаем OK или закрываем)
            print("\n=== Закрытие диалога L Series ===")
            try:
                ok_button = laser_setup_dialog.child_window(title='OK', class_name='Button')
                ok_button.click()
                print("[OK] Диалог 'L Series' закрыт (OK)")
            except:
                try:
                    laser_setup_dialog.close()
                    print("[OK] Диалог 'L Series' закрыт (Close)")
                except:
                    pass
            
            time.sleep(2)
            
            # Возвращаемся к диалогу Setup и нажимаем кнопку Advanced на вкладке System
            print("\n=== Работа с Advanced на вкладке System ===")
            
            # setup_dialog уже открыт, вкладку менять не нужно (мы уже на System)
            # Ищем кнопку Advanced в setup_dialog
            try:
                advanced_button = setup_dialog.child_window(title='Advanced...', class_name='Button')
                advanced_button.click()
                print("[OK] Нажата кнопка 'Advanced...' в Setup")
                
                time.sleep(2)
                
                # Открывается диалог Advanced Settings
                try:
                    advanced_dialog = app.window(title_re='.*Advanced.*')
                    advanced_dialog.wait('visible', timeout=5)
                    print("[OK] Диалог 'Advanced Settings' открыт")
                    
                    time.sleep(1)
                    
                    # Находим и заполняем поле Clock Frequency
                    print("\n=== Заполнение Clock Frequency ===")
                    frequency_value = row.get('frequency', '')
                    find_and_fill_edit(advanced_dialog, 'Clock Frequency', frequency_value)
                    print(f"[OK] 'Clock Frequency' заполнено: {frequency_value}")
                    
                    time.sleep(0.5)
                    
                    # Закрываем диалог Advanced
                    try:
                        ok_button = advanced_dialog.child_window(title='OK', class_name='Button')
                        ok_button.click()
                        print("[OK] Диалог 'Advanced Settings' закрыт (OK)")
                    except:
                        try:
                            advanced_dialog.close()
                            print("[OK] Диалог 'Advanced Settings' закрыт (Close)")
                        except:
                            pass
                    
                    time.sleep(1)
                    
                except Exception as e:
                    print(f"[FAIL] Диалог 'Advanced Settings' не открылся: {e}")
            
            except Exception as e:
                print(f"[FAIL] Кнопка 'Advanced' не найдена в Setup: {e}")
            
            time.sleep(1)
            
            # Переходим на вкладку Control
            print("\n=== Переход на вкладку Control ===")
            try:
                tab_control = setup_dialog.child_window(class_name='SysTabControl32')
                tab_control.select(3)  # 3 = Control tab (Information=0, System=1, Acquisition=2, Control=3)
                print("[OK] Переход на вкладку 'Control'")
                time.sleep(1)
            except Exception as e:
                print(f"[FAIL] Ошибка при переходе на Control: {e}")
            
            # Ищем группу Corrections и кнопку Setup
            print("\n=== Поиск группы Corrections и кнопки Setup ===")
            try:
                all_children = list(setup_dialog.children())
                
                # Находим GroupBox с названием Corrections
                corrections_group = None
                for child in all_children:
                    try:
                        if child.class_name() == 'Button' and child.window_text() == 'Corrections':
                            corrections_rect = child.rectangle()
                            corrections_group = (child, corrections_rect)
                            print(f"[OK] Найдена группа Corrections: top={corrections_rect.top}, left={corrections_rect.left}, right={corrections_rect.right}, bottom={corrections_rect.bottom}")
                            break
                    except:
                        pass
                
                if corrections_group:
                    corrections_group_obj, corrections_rect = corrections_group
                    
                    # Выводим все кнопки Setup в этой группе
                    print("\n=== Все кнопки Setup в группе Corrections ===")
                    setup_buttons_in_corrections = []
                    for child in all_children:
                        try:
                            if child.class_name() == 'Button' and 'Setup' in child.window_text():
                                child_rect = child.rectangle()
                                # Проверяем, находится ли кнопка в границах группы Corrections
                                if (child_rect.top > corrections_rect.top + 10 and 
                                    child_rect.bottom < corrections_rect.bottom - 10 and
                                    child_rect.left > corrections_rect.left + 10 and 
                                    child_rect.right < corrections_rect.right - 10):
                                    is_enabled = child.is_enabled()
                                    setup_buttons_in_corrections.append((child, child_rect))
                                    print(f"  Setup кнопка: title='{child.window_text()}', top={child_rect.top}, left={child_rect.left}, enabled={is_enabled}")
                        except:
                            pass
                    
                    if setup_buttons_in_corrections:
                        # Берем первую (верхнюю) кнопку Setup
                        setup_buttons_in_corrections.sort(key=lambda x: x[1].top)
                        first_setup_button = setup_buttons_in_corrections[0][0]
                        print(f"\n[OK] Найдена верхняя кнопка Setup: '{first_setup_button.window_text()}'")
                        
                        # Нажимаем кнопку Setup
                        print("\n=== Открытие диалога Corrections Setup ===")
                        first_setup_button.click()
                        print("[OK] Нажата верхняя кнопка Setup")
                        
                        time.sleep(2)
                        
                        # Ищем диалог Corrections Setup
                        try:
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
                            
                            print("\n=== Проверка заполнения Edit полей ===")
                            # Проверяем Edit поля
                            expected_values = {
                                'Baro. Fact': '0.3',
                                'Self Attraction Correction': '-0.58',
                                'Diffraction Correction': '1.2'
                            }
                            
                            # Ищем Edit поля и проверяем их значения
                            for control in all_controls:
                                try:
                                    if control.class_name() == 'Edit':
                                        current_value = control.window_text()
                                        print(f"  Edit поле с значением: '{current_value}'")
                                except:
                                    pass
                            
                            # Закрываем диалог
                            print("\n=== Закрытие диалога Corrections ===")
                            try:
                                ok_button = corrections_dialog.child_window(title='OK', class_name='Button')
                                ok_button.click()
                                print("[OK] Диалог 'Corrections Setup' закрыт (OK)")
                            except:
                                try:
                                    corrections_dialog.close()
                                    print("[OK] Диалог 'Corrections Setup' закрыт (Close)")
                                except:
                                    pass
                            
                            time.sleep(1)
                            
                        except Exception as e:
                            print(f"[FAIL] Диалог 'Corrections Setup' не открылся: {e}")
                            import traceback
                            traceback.print_exc()
                else:
                    print("[FAIL] Группа Corrections не найдена")
            
            except Exception as e:
                print(f"[FAIL] Ошибка при поиске Corrections: {e}")
                import traceback
                traceback.print_exc()
            
            # Ищем System Response Compensation и Uncertainty на Control tab
            print("\n=== Проверка System Response Compensation ===")
            all_controls = list(setup_dialog.children())
            
            # Ищем System Response Compensation checkbox
            sys_response_checkbox = None
            for control in all_controls:
                try:
                    if control.class_name() == 'Button' and 'System Response Compensation' in control.window_text():
                        sys_response_checkbox = control
                        is_checked = control.is_checked()
                        print(f"  'System Response Compensation': текущее состояние = {is_checked}")
                        
                        if is_checked:
                            control.click()
                            print(f"    [OK] Убрали галочку 'System Response Compensation'")
                            time.sleep(0.3)
                        break
                except:
                    pass
            
            if not sys_response_checkbox:
                print("  [FAIL] 'System Response Compensation' не найдена")
            
            # Ищем группу Uncertainty и кнопку Setup
            print("\n=== Поиск группы Uncertainty ===")
            uncertainty_setup_button = None
            
            # Сначала находим GroupBox Uncertainty
            for control in all_controls:
                try:
                    if control.class_name() == 'Button' and control.window_text() == 'Uncertainty':
                        uncertainty_rect = control.rectangle()
                        print(f"[OK] Найдена группа Uncertainty: top={uncertainty_rect.top}, left={uncertainty_rect.left}, right={uncertainty_rect.right}, bottom={uncertainty_rect.bottom}")
                        
                        # Теперь ищем кнопку Setup в этой группе
                        for child in all_controls:
                            try:
                                if child.class_name() == 'Button' and 'Setup' in child.window_text():
                                    child_rect = child.rectangle()
                                    # Проверяем, находится ли кнопка в границах группы Uncertainty
                                    if (child_rect.top > uncertainty_rect.top + 10 and 
                                        child_rect.bottom < uncertainty_rect.bottom - 10 and
                                        child_rect.left > uncertainty_rect.left + 10 and 
                                        child_rect.right < uncertainty_rect.right - 10):
                                        uncertainty_setup_button = (child, child_rect)
                                        print(f"  [OK] Найдена кнопка Setup в группе Uncertainty: top={child_rect.top}, left={child_rect.left}")
                                        break
                            except:
                                pass
                        break
                except:
                    pass
            
            if uncertainty_setup_button:
                print("\n=== Открытие диалога Uncertainties ===")
                uncertainty_button, _ = uncertainty_setup_button
                uncertainty_button.click()
                print("[OK] Нажата кнопка 'Setup' в группе Uncertainty")
                
                time.sleep(2)
                
                # Ищем диалог Uncertainties
                try:
                    uncertainties_dialog = app.window(title_re='.*Uncertainties.*')
                    uncertainties_dialog.wait('visible', timeout=5)
                    print("[OK] Диалог 'Uncertainties' открыт")
                    
                    time.sleep(1)
                    
                    # Заполняем поля Uncertainties согласно конфигу
                    print("\n=== Заполнение полей Uncertainties ===")
                    
                    uncertainties_values = config['uncertainties']
                    
                    all_unc_controls = list(uncertainties_dialog.children())
                    
                    # Находим все Static элементы с их labels и рядом находящиеся Edit элементы
                    for label_text, target_value in uncertainties_values.items():
                        try:
                            # Ищем Static с нужным label
                            static_elem = None
                            for control in all_unc_controls:
                                try:
                                    if control.class_name() == 'Static' and label_text in control.window_text():
                                        static_elem = control
                                        break
                                except:
                                    pass
                            
                            if static_elem:
                                static_rect = static_elem.rectangle()
                                
                                # Ищем ближайший Edit справа от Static
                                candidates = []
                                for control in all_unc_controls:
                                    try:
                                        if control.class_name() == 'Edit':
                                            child_rect = control.rectangle()
                                            # Проверяем, находится ли Edit справа и на одной строке со Static
                                            same_row = abs(child_rect.top - static_rect.top) < 12
                                            is_to_the_right = child_rect.left > static_rect.right
                                            
                                            if same_row and is_to_the_right:
                                                distance = child_rect.left - static_rect.right
                                                candidates.append((distance, control))
                                    except:
                                        pass
                                
                                if candidates:
                                    candidates.sort(key=lambda x: x[0])
                                    closest_edit = candidates[0][1]
                                    closest_edit.set_text(target_value)
                                    print(f"[OK] '{label_text}' заполнено: {target_value}")
                                    time.sleep(0.2)
                            else:
                                print(f"[FAIL] Label '{label_text}' не найден")
                        except Exception as e:
                            print(f"[FAIL] Ошибка при заполнении '{label_text}': {e}")
                    
                    print("\n=== Закрытие диалога Uncertainties ===")
                    time.sleep(1)
                    
                    # Нажимаем кнопку Update перед закрытием
                    try:
                        update_button = uncertainties_dialog.child_window(title='Update', class_name='Button')
                        update_button.click()
                        print("[OK] Нажата кнопка 'Update'")
                        time.sleep(1)  # Даем приложению время обработать Update
                    except Exception as e:
                        print(f"[INFO] Кнопка 'Update' не найдена: {e}")
                    
                    # Закрываем диалог Uncertainties нажатием кнопки OK
                    print("\n=== Закрытие диалога Uncertainties ===")
                    try:
                        # Выводим все кнопки для отладки
                        all_buttons = []
                        for control in uncertainties_dialog.children():
                            try:
                                if control.class_name() == 'Button':
                                    all_buttons.append(control.window_text())
                                    print(f"  Найдена кнопка: '{control.window_text()}'")
                            except:
                                pass
                        
                        # Ищем кнопку OK или Close
                        ok_button = None
                        for control in uncertainties_dialog.children():
                            try:
                                if control.class_name() == 'Button':
                                    button_text = control.window_text()
                                    if button_text in ['OK', 'Close', 'Закрыть', 'ОК']:
                                        ok_button = control
                                        break
                            except:
                                pass
                        
                        if ok_button:
                            ok_button.click()
                            print(f"[OK] Диалог 'Uncertainties' закрыт (нажата кнопка '{ok_button.window_text()}')")
                            time.sleep(2)
                        else:
                            print("[FAIL] Кнопка OK/Close не найдена")
                            if all_buttons:
                                print(f"  Доступные кнопки: {all_buttons}")
                    except Exception as e:
                        print(f"[FAIL] Ошибка при закрытии Uncertainties: {e}")
                        import traceback
                        traceback.print_exc()
                    
                    time.sleep(2)
                    
                    # Переходим на вкладку Comments
                    print("\n=== Переход на вкладку Comments ===")
                    
                    # Даем установке время убедиться, что диалог закрыт
                    time.sleep(2)
                    
                    try:
                        # Убеждаемся, что Setup диалог все еще активен
                        setup_dialog.set_focus()
                        time.sleep(0.5)
                        
                        tab_control = setup_dialog.child_window(class_name='SysTabControl32')
                        tab_control.select(4)  # 4 = Comments tab
                        print("[OK] Переход на вкладку 'Comments'")
                        time.sleep(1)
                    except Exception as e:
                        print(f"[FAIL] Ошибка при переходе на Comments: {e}")
                    
                    # Заполняем поля на вкладке Comments
                    print("\n=== Заполнение полей Comments ===")
                    
                    all_controls = list(setup_dialog.children())
                    
                    # Заполняем Company/Institution
                    try:
                        # Ищем Static element "Company/Institution:"
                        company_static = None
                        for control in all_controls:
                            try:
                                if control.class_name() == 'Static' and 'Company/Institution' in control.window_text():
                                    company_static = control
                                    break
                            except:
                                pass
                        
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
                        else:
                            print("[FAIL] Static 'Company/Institution' не найден")
                    except Exception as e:
                        print(f"[FAIL] Ошибка при заполнении Company/Institution: {e}")
                        import traceback
                        traceback.print_exc()
                    
                    # Заполняем большое поле Comments
                    try:
                        comments_text = row.get('comments', '')
                        if comments_text:
                            # Ищем большое Edit поле для комментариев (height > 150)
                            large_edits = []
                            for control in all_controls:
                                try:
                                    if control.class_name() == 'Edit':
                                        rect = control.rectangle()
                                        height = rect.bottom - rect.top
                                        width = rect.right - rect.left
                                        # Ищем поле с большой высотой
                                        if height > 150:
                                            large_edits.append((control, rect, height, width))
                                except:
                                    pass
                            
                            if large_edits:
                                # Берем первое крупное поле
                                large_edits.sort(key=lambda x: x[2], reverse=True)
                                comments_edit = large_edits[0][0]
                                
                                # Очищаем поле и вводим новое значение
                                comments_edit.send_keystrokes('^a')  # Select all
                                time.sleep(0.1)
                                
                                # Разделяем текст по переводам строк и вводим с Ctrl+Enter между ними
                                lines = comments_text.split('\n')
                                comments_edit.set_text(lines[0])  # Первая строка
                                time.sleep(0.1)
                                
                                # Остальные строки вводим после Ctrl+Enter
                                for line in lines[1:]:
                                    comments_edit.send_keystrokes('^{ENTER}')  # Ctrl+Enter для новой строки
                                    time.sleep(0.2)
                                    comments_edit.type_keys(line)  # Вводим текст строки
                                    time.sleep(0.1)
                                
                                time.sleep(0.5)
                                
                                # Отправляем фокус из поля
                                comments_edit.send_keystrokes('{TAB}')
                                time.sleep(0.3)
                                
                                print(f"[OK] Поле Comments заполнено ({len(comments_text)} символов, {len(lines)} строк)")
                            else:
                                print("[INFO] Большое поле для Comments не найдено")
                        else:
                            print("[INFO] comments_text пуста")
                    except Exception as e:
                        print(f"[FAIL] Ошибка при заполнении Comments: {e}")
                    
                    time.sleep(1)
                    
                    # Теперь закрываем диалог Setup
                    print("\n=== Закрытие диалога Setup ===")
                    try:
                        # Нажимаем OK через Return вместо click()
                        setup_dialog.send_keystrokes('{ENTER}')
                        print("[OK] Диалог 'Setup' закрыт (ENTER)")
                        time.sleep(2)
                    except Exception as e:
                        print(f"  Попытка 1 (ENTER) не прошла: {e}")
                        try:
                            # Попытка найти и нажать кнопку OK
                            ok_button = setup_dialog.child_window(title='OK', class_name='Button')
                            ok_button.press_button()
                            print("[OK] Диалог 'Setup' закрыт (press_button)")
                            time.sleep(2)
                        except Exception as e2:
                            print(f"  Попытка 2 не прошла: {e2}")
                            try:
                                setup_dialog.close()
                                print("[OK] Диалог 'Setup' закрыт (Close)")
                                time.sleep(2)
                            except Exception as e3:
                                print(f"  Попытка 3 не прошла: {e3}")
                    
                    time.sleep(1)
                    
                except Exception as e:
                    print(f"[FAIL] Диалог 'Uncertainties' не открылся: {e}")
                    import traceback
                    traceback.print_exc()
            else:
                print("[FAIL] Кнопка Setup в группе Uncertainty не найдена")
            
            time.sleep(1)
        
        except Exception as e:
            print(f"[FAIL] Ошибка при работе с Laser Setup: {e}")
            import traceback
            traceback.print_exc()
        
        
    except Exception as e:
        print(f"Ошибка при открытии диалога: {e}")
        import traceback
        traceback.print_exc()
        # Выводим все окна приложения для отладки
        for window in app.windows():
            print(f"Окно: {window.window_text()}, класс: {window.class_name()}")

