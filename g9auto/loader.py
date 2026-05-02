import pandas as pd
from datetime import datetime as dt
from datetime import time as tm

def read_project(path_to_file):
    with open(path_to_file, 'r', encoding='cp1251') as project_file:
        result = {}
        for line in project_file:
            line = line.strip()
            match line:
                # case 'Delta Factors':
                #     columns=project_file.readline().split()
                #     print(columns)
                #     delta_factors = pd.DataFrame(columns=columns)
                #     for delta_index in range(12):
                #         delta_factors = pd.concat([delta_factors, pd.DataFrame([project_file.readline().split()], columns=columns, index=[delta_index])])
                #     value_name = 'Coeffs'
                #     # result.loc[index, multindex] = 'delta_factors'
                #     for i in range(4):
                #         delta_factors_line =  project_file.readline()
                #         items = delta_factors_line.strip().split(':')
                #         value_name = items[0]
                #         match value_name:
                #             case 'Ocean Load ON, Filename':
                #                 value = ':'.join(items[1:])
                #                 value_unit = ''
                #             case 'Waves':
                #                 value = [[i] for i in items[1].split()]
                #                 value_unit = ''
                #             case 'Amplitude (µGal)' | 'Phase (deg)':
                #                 value_name, value_unit = value_name.split()
                #                 value_unit = value_unit.strip('(').strip(')')
                #                 value = [[float(i)] for i in items[1].split()]
                #         multindex = (line, value_name, value_unit)
                #         # result[multindex] = None
                #         # result.loc[index, multindex] = value
                #         result[multindex] = value

                case 'Comments':
                    comments = []
                    eof = True
                    while eof:
                        comment_line = project_file.readline()
                        if comment_line:
                            comments.append(comment_line)
                        else:
                            eof = False
                    value_unit = ''
                    multindex = (line, value_name, value_unit)
                    # result[multindex] = None
                    # result.loc[index, multindex] = ''.join(comments)
                    result[multindex] = ''.join(comments)
                case 'Micro-g LaCoste g Processing Report': 
                    for i in range(8):
                        micro_g_laCoste_g_processing_report_line = project_file.readline()
                        items = micro_g_laCoste_g_processing_report_line.strip().split(':')
                        value_name = items[0]
                        value_unit = ''
                        match value_name:
                            case 'File Created':
                                value = dt.strptime(':'.join(items[1:]).strip(), '%m/%d/%y, %H:%M:%S')
                            case '':
                                continue
                            case _:
                                value = items[1]
                        multindex = (line, value_name, value_unit)
                        # result[multindex] = None
                        result[multindex] = value
                case 'Station Data': 
                    for i in range(10):
                        station_data_line = project_file.readline()
                        items = station_data_line.strip().split(':')
                        value_name = items[0]
                        match value_name:
                            case 'Name' | 'Site Code':
                                value = items[1]
                            case 'Lat':
                                multindex = (line, 'Latitude', 'deg')
                                # result[multindex] = None
                                result[multindex] = float(items[1].split()[0])
                                multindex = (line, 'Longitude', 'deg')
                                # result[multindex] = None
                                result[multindex] = float(items[2].split()[0])
                                value, value_unit = items[3].split()
                                multindex = (line, 'Elevation', value_unit)
                                # result[multindex] = None
                                result[multindex] = float(value)
                                continue
                            case 'Barometric Admittance Factor':
                                value = float(items[1])
                                value_unit = ''
                            case 'Polar Motion Coord':
                                polar_string = items[1].split()
                                multindex = (line, f'{value_name} x', polar_string[1])
                                # result[multindex] = None
                                result[multindex] = float(polar_string[0])
                                multindex = (line, f'{value_name} x', polar_string[1])
                                # result[multindex] = None
                                result[multindex] = float(polar_string[2])
                                continue
                            case _:
                                value, value_unit = items[1].split()
                                value = float(value)
                        multindex = (line, value_name, value_unit)
                        # result[multindex] = None
                        result[multindex] = value
                case 'Earth Tide (ETGTAB) Selected': 
                    for i in range(2):
                        earth_tide_selected_line = project_file.readline()
                        items = earth_tide_selected_line.strip().split(':')
                        value_name = items[0]
                        value_unit = ''
                        value = ':'.join(items[1:])
                        multindex = (line, value_name, value_unit)
                        # result[multindex] = None
                        result[multindex] = value
                case 'Instrument Data': 
                    for i in range(8):
                        instrument_data_line = project_file.readline()
                        items = instrument_data_line.strip().split(':')
                        value_name = items[0]
                        value_unit = ''
                        match value_name:
                            case 'Meter Type' | 'Meter S/N' | 'Laser':
                                value = items[1]
                            case _:
                                value, value_unit = items[1].split()
                                value = float(value)
                        multindex = (line, value_name, value_unit)
                        # result[multindex] = None
                        result[multindex] = value
                case 'Processing Results': 
                    for i in range(22):
                        processing_results_line = project_file.readline()
                        items = processing_results_line.strip().split(':')
                        value_name = items[0]
                        value_unit = ''
                        match value_name:
                            case 'Date':
                                processing_date = items[1].strip()
                            case 'Time':
                                processing_time = ':'.join(items[1:]).strip()
                                value = dt.strptime(f'{processing_date} {processing_time}', '%m/%d/%y %H:%M:%S')
                                value_name = 'Date Time'
                            case 'Time Offset (D h':
                                value_name = ':'.join(items[:3])
                                value = tm(int(items[3].split()[0]), int(items[3].split()[1]), int(items[4]), int(items[5]))
                            case 'Gravity' | 'Set Scatter' | 'Measurement Precision' | 'Total Uncertainty' | 'Red/Blue Separation':
                                value, value_unit = items[1].split()
                                value = float(value)
                            case 'Set #s Processed':
                                value = [[int(i)] for i in items[1].split(',')]
                            case 'Set #s NOT Processed':
                                if len(items) > 2:
                                    value = int(items[1])
                            case _:
                                value = int(items[1])
                        multindex = (line, value_name, value_unit)
                        # result[multindex] = None
                        result[multindex] = value
                case 'Acquisition Settings': 
                    for i in range(5):
                        acquisition_settings_line = project_file.readline()
                        items = acquisition_settings_line.strip().split(':')
                        value_name = items[0]
                        value_unit = ''
                        match value_name:
                            case 'Number of Sets' | 'Number of Drops':
                                value = int(items[1])
                            case _:
                                value, value_unit = items[1].split()
                                value = int(value)
                        multindex = (line, value_name, value_unit)
                        # result[multindex] = None
                        result[multindex] = value
                case 'Frequency Response Enabled': 
                    for i in range(3):
                        frequency_response_enabled_line = project_file.readline()
                        items = frequency_response_enabled_line.strip().split(':')
                        value_name = items[0]
                        value_unit = ''
                        match value_name:
                            case 'Maximum Terms':
                                value = int(items[1])
                            case 'Minimum Frequency':
                                value, value_unit = items[1].split()
                                value = float(value)
                            case 'Significance Threshold':
                                value = float(items[1])
                        multindex = (line, value_name, value_unit)
                        # result[multindex] = None
                        result[multindex] = value
                case 'Gravity Corrections': 
                    for i in range(5):
                        gravity_corrections_line = project_file.readline()
                        items = gravity_corrections_line.strip().split(':')
                        value_name = items[0]
                        value, value_unit = items[1].split()
                        multindex = (line, value_name, value_unit)
                        result[multindex] = float(value)
                case 'Uncertainties':
                    for i in range(15):
                        uncertaintes_line = project_file.readline()
                        items = uncertaintes_line.strip().split(':')
                        value_name = items[0]
                        match value_name:
                            case 'Sigma Reject' | 'Earth Tide Factor' | 'Ocean Load Factor':
                                value = items[1]
                                multindex = (line, value_name, '')
                                # result[multindex] = None
                                result[multindex] = float(value)
                            case 'Gradient':
                                value_1, value_unit_1, value_2, value_unit_2 = items[1].split()
                                value_2 = value_2.replace('(', '')
                                value_unit_2 = value_unit_2.replace(')', '')
                                multindex = (line, value_name, value_unit_1)
                                # result[multindex] = None
                                result[multindex] = float(value_1)
                                multindex = (line, value_name, value_unit_2)
                                # result[multindex] = None
                                result[multindex] = float(value_2)
                            case _:
                                value, value_unit = items[1].split()
                                multindex = (line, value_name, value_unit)
                                # result[multindex] = None
                                result[multindex] = float(value)
        project_file.close()
        # result.columns = pd.MultiIndex.from_tuples(result.columns, names=['Groups', 'Values', 'Units'])
        return result, ['Groups', 'Values', 'Units']
