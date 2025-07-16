#!/usr/bin/env python3
"""
Zaawansowany analizator plików PXF
Specjalizuje się w formatach PMLPXF i innych wariantach PXF
"""

import struct
import logging
import re
from typing import Dict, List, Any, Optional, Tuple

class PXFAnalyzer:
    """Klasa do zaawansowanej analizy plików PXF"""
    
    def __init__(self, data: bytes):
        self.data = data
        self.file_size = len(data)
        self.header_info = {}
        self.sections = {}
        self.parameters = {}
        
    def analyze(self) -> Dict[str, Any]:
        """Główna metoda analizy pliku PXF"""
        results = {
            'file_format': 'Unknown',
            'header_analysis': {},
            'sections_found': {},
            'embroidery_parameters': {},
            'stitch_data': {},
            'machine_settings': {},
            'technical_specs': {},
            'analysis_success': False
        }
        
        try:
            # Identyfikacja formatu
            format_info = self._identify_format()
            results['file_format'] = format_info
            
            # Analiza nagłówka
            if format_info['type'] == 'PMLPXF':
                results['header_analysis'] = self._analyze_pmlpxf_header()
                results['sections_found'] = self._find_pmlpxf_sections()
                results['embroidery_parameters'] = self._extract_pmlpxf_parameters()
            else:
                # Analiza generyczna dla innych formatów PXF
                results['header_analysis'] = self._analyze_generic_pxf()
                results['embroidery_parameters'] = self._extract_generic_parameters()
            
            # Analiza danych ściegów
            results['stitch_data'] = self._analyze_stitch_data()
            
            # Analiza ustawień maszyny
            results['machine_settings'] = self._extract_machine_settings()
            
            # Specyfikacje techniczne
            results['technical_specs'] = self._calculate_technical_specs()
            
            results['analysis_success'] = True
            
        except Exception as e:
            logging.error(f"Błąd w analizie PXF: {e}")
            results['error'] = str(e)
        
        return results
    
    def _identify_format(self) -> Dict[str, str]:
        """Identyfikuje typ formatu PXF"""
        if self.data.startswith(b'PMLPXF'):
            version = self.data[6:8]
            return {
                'type': 'PMLPXF',
                'version': version.decode('ascii', errors='ignore'),
                'description': 'Tajima PMLPXF format'
            }
        elif self.data.startswith(b'PXF'):
            return {
                'type': 'PXF',
                'version': 'Unknown',
                'description': 'Generic PXF format'
            }
        else:
            return {
                'type': 'Unknown',
                'version': 'Unknown',
                'description': 'Nieznany format PXF'
            }
    
    def _analyze_pmlpxf_header(self) -> Dict[str, Any]:
        """Analizuje nagłówek PMLPXF"""
        header = {}
        
        if len(self.data) < 64:
            return {'error': 'Plik za mały dla pełnego nagłówka'}
        
        try:
            # Podstawowe informacje z nagłówka
            header['signature'] = self.data[0:8].decode('ascii', errors='ignore')
            
            # Rozmiar nagłówka (offset 8-12)
            header_size = struct.unpack('<I', self.data[8:12])[0]
            header['header_size'] = header_size
            
            # Rozmiar danych (offset 12-16)
            if len(self.data) >= 16:
                data_size = struct.unpack('<I', self.data[12:16])[0]
                header['data_size'] = data_size
            
            # Wymiary wzoru (offset 16-32)
            if len(self.data) >= 32:
                dims = struct.unpack('<4I', self.data[16:32])
                header['dimensions'] = {
                    'width': dims[0] / 100.0,  # w mm
                    'height': dims[1] / 100.0,  # w mm
                    'x_offset': dims[2] / 100.0,
                    'y_offset': dims[3] / 100.0
                }
            
            # Liczba kolorów (offset 32-36)
            if len(self.data) >= 36:
                color_count = struct.unpack('<I', self.data[32:36])[0]
                header['color_count'] = color_count
            
            # Liczba ściegów (offset 36-40)
            if len(self.data) >= 40:
                stitch_count = struct.unpack('<I', self.data[36:40])[0]
                header['stitch_count'] = stitch_count
            
            # Flagi formatu (offset 40-44)
            if len(self.data) >= 44:
                flags = struct.unpack('<I', self.data[40:44])[0]
                header['format_flags'] = flags
                header['has_underlay'] = bool(flags & 0x01)
                header['has_applique'] = bool(flags & 0x02)
                header['has_sequins'] = bool(flags & 0x04)
            
        except struct.error as e:
            header['error'] = f'Błąd parsowania nagłówka: {e}'
        
        return header
    
    def _find_pmlpxf_sections(self) -> Dict[str, Any]:
        """Znajduje sekcje w pliku PMLPXF"""
        sections = {}
        
        try:
            # Sekcja kolorów
            color_section = self._find_color_section()
            if color_section:
                sections['colors'] = color_section
            
            # Sekcja ściegów
            stitch_section = self._find_stitch_section()
            if stitch_section:
                sections['stitches'] = stitch_section
            
            # Sekcja metadanych
            metadata_section = self._find_metadata_section()
            if metadata_section:
                sections['metadata'] = metadata_section
            
        except Exception as e:
            sections['error'] = f'Błąd wyszukiwania sekcji: {e}'
        
        return sections
    
    def _find_color_section(self) -> Optional[Dict[str, Any]]:
        """Znajduje sekcję kolorów w pliku"""
        for i in range(0, len(self.data) - 16):
            # Szukamy znaczników kolorów
            if self.data[i:i+4] == b'CLRS' or self.data[i:i+4] == b'COLR':
                try:
                    # Liczba kolorów
                    color_count = struct.unpack('<I', self.data[i+4:i+8])[0]
                    if 1 <= color_count <= 256:  # Rozsądna liczba kolorów
                        colors = []
                        offset = i + 8
                        
                        for j in range(color_count):
                            if offset + 4 <= len(self.data):
                                # RGB + alfa lub indeks
                                color_data = struct.unpack('<I', self.data[offset:offset+4])[0]
                                colors.append({
                                    'index': j,
                                    'rgb': f"#{color_data:06X}",
                                    'raw_value': color_data
                                })
                                offset += 4
                        
                        return {
                            'position': i,
                            'count': color_count,
                            'colors': colors
                        }
                except struct.error:
                    continue
        
        return None
    
    def _find_stitch_section(self) -> Optional[Dict[str, Any]]:
        """Znajduje sekcję ściegów"""
        for i in range(0, len(self.data) - 16):
            if self.data[i:i+4] == b'STCH' or self.data[i:i+4] == b'STITCHES':
                try:
                    stitch_count = struct.unpack('<I', self.data[i+4:i+8])[0]
                    if 1 <= stitch_count <= 1000000:  # Rozsądna liczba ściegów
                        return {
                            'position': i,
                            'count': stitch_count,
                            'data_start': i + 8
                        }
                except struct.error:
                    continue
        
        return None
    
    def _find_metadata_section(self) -> Optional[Dict[str, Any]]:
        """Znajduje sekcję metadanych"""
        metadata = {}
        
        # Szukamy różnych znaczników metadanych
        markers = [
            b'Created',
            b'Software',
            b'Tajima',
            b'DG/ML',
            b'Version',
            b'Author',
            b'Description'
        ]
        
        for marker in markers:
            pos = self.data.find(marker)
            if pos != -1:
                # Wyciągamy tekst wokół znacznika
                start = max(0, pos - 20)
                end = min(len(self.data), pos + 200)
                text = self.data[start:end].decode('utf-8', errors='ignore')
                metadata[marker.decode()] = text.strip()
        
        return metadata if metadata else None
    
    def _extract_pmlpxf_parameters(self) -> Dict[str, Any]:
        """Wyciąga parametry haftu z pliku PMLPXF"""
        params = {}
        
        try:
            # Przechowuje wszystkie znalezione parametry z maksymalną szczegółowością
            all_parameters = {
                'density_values': [],
                'underlay_types': [],
                'compensation_values': [],
                'fill_angles': [],
                'stitch_types': [],
                'thread_tensions': [],
                'stitch_lengths': [],
                'machine_speeds': [],
                'pull_compensations': [],
                'auto_underlay_settings': [],
                'pattern_densities': [],
                'thread_weights': [],
                'needle_sizes': [],
                'fabric_types': [],
                'hoop_sizes': [],
                'stabilizer_types': [],
                'embroidery_speeds': [],
                'trim_commands': [],
                'color_change_counts': []
            }
            
            # Szukamy sekcji parametrów z maksymalną dokładnością (każdy bajt + większe okno)
            for i in range(0, len(self.data) - 64, 1):  # Analizujemy każdy bajt z większym oknem
                chunk = self.data[i:i+64]  # Większy chunk dla lepszego wykrywania
                
                # Parametry gęstości
                if b'DENSITY' in chunk:
                    try:
                        density = struct.unpack('<f', self.data[i+8:i+12])[0]
                        if 0.1 <= density <= 20:
                            # Konwertuj na cm
                            density_cm = density / 10.0
                            all_parameters['density_values'].append(density_cm)
                    except struct.error:
                        pass
                
                # Parametry podkładu
                if b'UNDERLAY' in chunk:
                    try:
                        underlay_type = struct.unpack('<I', self.data[i+8:i+12])[0]
                        underlay_map = {
                            0: 'None',
                            1: 'Edge Run',
                            2: 'Zigzag',
                            3: 'Tatami',
                            4: 'Automatic'
                        }
                        underlay_name = underlay_map.get(underlay_type, 'Unknown')
                        if underlay_name not in all_parameters['underlay_types']:
                            all_parameters['underlay_types'].append(underlay_name)
                    except struct.error:
                        pass
                
                # Kompensacja
                if b'COMPENSATION' in chunk or b'PULL' in chunk:
                    try:
                        compensation = struct.unpack('<f', self.data[i+8:i+12])[0]
                        if -50 <= compensation <= 50:
                            all_parameters['compensation_values'].append(compensation)
                    except struct.error:
                        pass
                
                # Kąt wypełnienia
                if b'ANGLE' in chunk or b'FILL_ANGLE' in chunk:
                    try:
                        angle = struct.unpack('<f', self.data[i+8:i+12])[0]
                        if -180 <= angle <= 180:
                            all_parameters['fill_angles'].append(angle)
                    except struct.error:
                        pass
                
                # Typy ściegów
                if b'STITCH_TYPE' in chunk or b'FILL_TYPE' in chunk:
                    try:
                        stitch_type = struct.unpack('<I', self.data[i+8:i+12])[0]
                        stitch_map = {
                            0: 'Running',
                            1: 'Satin',
                            2: 'Fill',
                            3: 'Tatami',
                            4: 'Cross Stitch',
                            5: 'Bean Stitch'
                        }
                        stitch_name = stitch_map.get(stitch_type, f'Type {stitch_type}')
                        if stitch_name not in all_parameters['stitch_types']:
                            all_parameters['stitch_types'].append(stitch_name)
                    except struct.error:
                        pass
                
                # Naprężenie nici
                if b'TENSION' in chunk:
                    try:
                        tension = struct.unpack('<f', self.data[i+8:i+12])[0]
                        if 0 <= tension <= 100:
                            all_parameters['thread_tensions'].append(tension)
                    except struct.error:
                        pass
                
                # Dodatkowe parametry długości ściegów
                if b'STITCH_LENGTH' in chunk or b'LENGTH' in chunk:
                    try:
                        length = struct.unpack('<f', self.data[i+8:i+12])[0]
                        if 0.1 <= length <= 10:  # Rozsądne długości ściegów w mm
                            all_parameters['stitch_lengths'].append(length / 10.0)  # Konwersja na cm
                    except struct.error:
                        pass
                
                # Prędkość maszyny (dodatkowe wykrywanie)
                if b'SPEED' in chunk or b'MACHINE_SPEED' in chunk:
                    try:
                        speed = struct.unpack('<I', self.data[i+8:i+12])[0]
                        if 100 <= speed <= 2000:
                            all_parameters['machine_speeds'].append(speed)
                    except struct.error:
                        pass
                
                # Automatyczny podkład
                if b'AUTO_UNDERLAY' in chunk or b'AUTOMATIC' in chunk:
                    try:
                        auto_setting = struct.unpack('<I', self.data[i+8:i+12])[0]
                        if auto_setting in [0, 1]:
                            setting_name = 'Włączony' if auto_setting == 1 else 'Wyłączony'
                            all_parameters['auto_underlay_settings'].append(setting_name)
                    except struct.error:
                        pass
                
                # Dodatkowe zaawansowane parametry
                if b'THREAD_WEIGHT' in chunk or b'WEIGHT' in chunk:
                    try:
                        weight = struct.unpack('<I', self.data[i+8:i+12])[0]
                        if 30 <= weight <= 120:  # Typowe wagi nici
                            all_parameters['thread_weights'].append(weight)
                    except struct.error:
                        pass
                
                if b'NEEDLE_SIZE' in chunk or b'NEEDLE' in chunk:
                    try:
                        needle = struct.unpack('<I', self.data[i+8:i+12])[0]
                        if 60 <= needle <= 120:  # Typowe rozmiary igieł
                            all_parameters['needle_sizes'].append(needle)
                    except struct.error:
                        pass
                
                if b'FABRIC_TYPE' in chunk or b'FABRIC' in chunk:
                    try:
                        fabric_code = struct.unpack('<I', self.data[i+8:i+12])[0]
                        fabric_types = {
                            1: 'Cotton', 2: 'Polyester', 3: 'Silk', 4: 'Denim',
                            5: 'Leather', 6: 'Canvas', 7: 'Fleece', 8: 'Terry'
                        }
                        if fabric_code in fabric_types:
                            all_parameters['fabric_types'].append(fabric_types[fabric_code])
                    except struct.error:
                        pass
                
                if b'HOOP_SIZE' in chunk or b'HOOP' in chunk:
                    try:
                        hoop = struct.unpack('<f', self.data[i+8:i+12])[0]
                        if 50 <= hoop <= 400:  # mm
                            all_parameters['hoop_sizes'].append(hoop / 10.0)  # Konwersja na cm
                    except struct.error:
                        pass
                
                if b'STABILIZER' in chunk:
                    try:
                        stab_type = struct.unpack('<I', self.data[i+8:i+12])[0]
                        stabilizers = {
                            0: 'None', 1: 'Tear-away', 2: 'Cut-away', 
                            3: 'Wash-away', 4: 'Heat-away', 5: 'Sticky'
                        }
                        if stab_type in stabilizers:
                            all_parameters['stabilizer_types'].append(stabilizers[stab_type])
                    except struct.error:
                        pass
            
            # Przetwarza zebrane parametry
            if all_parameters['density_values']:
                densities = all_parameters['density_values']
                if len(densities) == 1:
                    params['row_spacing'] = f"{densities[0]:.2f} cm"
                else:
                    params['row_spacing'] = f"{min(densities):.2f} - {max(densities):.2f} cm (różne wzory)"
            
            if all_parameters['underlay_types']:
                params['underlay_type'] = ', '.join(all_parameters['underlay_types'])
            
            if all_parameters['compensation_values']:
                compensations = all_parameters['compensation_values']
                if len(compensations) == 1:
                    params['pull_compensation'] = f"{compensations[0]:.1f}%"
                else:
                    params['pull_compensation'] = f"{min(compensations):.1f}% - {max(compensations):.1f}% (różne wzory)"
            
            if all_parameters['fill_angles']:
                angles = all_parameters['fill_angles']
                if len(angles) == 1:
                    params['fill_angle'] = f"{angles[0]:.0f}°"
                else:
                    unique_angles = list(set(angles))
                    if len(unique_angles) <= 3:
                        params['fill_angle'] = f"{', '.join([f'{a:.0f}°' for a in unique_angles])}"
                    else:
                        params['fill_angle'] = f"{len(unique_angles)} różnych kątów"
            
            if all_parameters['stitch_types']:
                params['stitch_types'] = ', '.join(all_parameters['stitch_types'])
            
            if all_parameters['thread_tensions']:
                tensions = all_parameters['thread_tensions']
                if len(tensions) == 1:
                    params['thread_tension'] = f"Level {tensions[0]:.0f}"
                else:
                    params['thread_tension'] = f"Level {min(tensions):.0f} - {max(tensions):.0f}"
            
            # Dodatkowe parametry
            if all_parameters['stitch_lengths']:
                lengths = all_parameters['stitch_lengths']
                if len(lengths) == 1:
                    params['stitch_length'] = f"{lengths[0]:.2f} cm"
                else:
                    params['stitch_length'] = f"{min(lengths):.2f} - {max(lengths):.2f} cm"
            
            if all_parameters['machine_speeds']:
                speeds = all_parameters['machine_speeds']
                if len(speeds) == 1:
                    params['machine_speed'] = f"{speeds[0]} spm"
                else:
                    params['machine_speed'] = f"{min(speeds)} - {max(speeds)} spm"
            
            if all_parameters['auto_underlay_settings']:
                params['auto_underlay'] = ', '.join(set(all_parameters['auto_underlay_settings']))
            
            # Dodatkowe zaawansowane parametry
            if all_parameters['thread_weights']:
                weights = all_parameters['thread_weights']
                if len(weights) == 1:
                    params['thread_weight'] = f"Wt {weights[0]}"
                else:
                    params['thread_weight'] = f"Wt {min(weights)} - {max(weights)}"
            
            if all_parameters['needle_sizes']:
                needles = all_parameters['needle_sizes']
                if len(needles) == 1:
                    params['needle_size'] = f"#{needles[0]}"
                else:
                    params['needle_size'] = f"#{min(needles)} - #{max(needles)}"
            
            if all_parameters['fabric_types']:
                params['fabric_type'] = ', '.join(set(all_parameters['fabric_types']))
            
            if all_parameters['hoop_sizes']:
                hoops = all_parameters['hoop_sizes']
                if len(hoops) == 1:
                    params['hoop_size'] = f"{hoops[0]:.1f} cm"
                else:
                    params['hoop_size'] = f"{min(hoops):.1f} - {max(hoops):.1f} cm"
            
            if all_parameters['stabilizer_types']:
                params['stabilizer_type'] = ', '.join(set(all_parameters['stabilizer_types']))
            
            # Dodaj informację o liczbie znalezionych parametrów
            total_params = sum(len(v) for v in all_parameters.values() if isinstance(v, list))
            params['parameters_found'] = total_params
            
            # Jeśli znaleziono wiele różnych wartości, dodaj ostrzeżenie
            varied_params = sum(1 for v in all_parameters.values() if isinstance(v, list) and len(v) > 1)
            if varied_params > 0:
                params['multi_pattern_note'] = f"Znaleziono {varied_params} parametrów z różnymi wartościami - prawdopodobnie wiele wzorów"
        
        except Exception as e:
            params['error'] = f'Błąd wyciągania parametrów: {e}'
        
        return params
    
    def _analyze_generic_pxf(self) -> Dict[str, Any]:
        """Analiza generyczna dla nieznanych formatów PXF"""
        analysis = {}
        
        # Podstawowe informacje
        analysis['file_size'] = self.file_size
        analysis['first_bytes'] = self.data[:32].hex()
        
        # Szukamy wzorców tekstowych
        text_content = self.data.decode('utf-8', errors='ignore')
        
        # Informacje o oprogramowaniu
        software_patterns = [
            r'Tajima\s+(\S+)',
            r'DG/ML\s+(\S+)',
            r'Version\s+(\S+)',
            r'Pulse\s+(\S+)'
        ]
        
        for pattern in software_patterns:
            match = re.search(pattern, text_content, re.IGNORECASE)
            if match:
                analysis['software'] = match.group(0)
                break
        
        return analysis
    
    def _extract_generic_parameters(self) -> Dict[str, Any]:
        """Wyciąga parametry z generycznego pliku PXF"""
        params = {}
        
        # Analiza tekstu
        text_content = self.data.decode('utf-8', errors='ignore')
        
        # Wzorce do wyszukania
        patterns = {
            'density': r'density[:\s]*(\d+\.?\d*)',
            'underlay': r'underlay[:\s]*(\w+)',
            'compensation': r'compensation[:\s]*(\d+\.?\d*)',
            'angle': r'angle[:\s]*(\d+\.?\d*)'
        }
        
        for param, pattern in patterns.items():
            match = re.search(pattern, text_content, re.IGNORECASE)
            if match:
                params[param] = match.group(1)
        
        return params
    
    def _analyze_stitch_data(self) -> Dict[str, Any]:
        """Analizuje dane ściegów z wykrywaniem wielu wzorów"""
        stitch_data = {}
        
        # Szukamy współrzędnych ściegów z większą precyzją
        coordinates = []
        patterns = []
        
        # Analizujemy większy zakres danych
        for i in range(0, len(self.data) - 6, 1):  # Co 1 bajt zamiast co 2
            try:
                x = struct.unpack('<h', self.data[i:i+2])[0]
                y = struct.unpack('<h', self.data[i+2:i+4])[0]
                cmd = struct.unpack('<H', self.data[i+4:i+6])[0]
                
                if -32000 < x < 32000 and -32000 < y < 32000:
                    coordinates.append((x, y, cmd))
                    
                    if len(coordinates) >= 30000:  # Maksymalny limit dla ultra-szczegółowej analizy
                        break
                        
            except struct.error:
                continue
        
        if coordinates:
            stitch_data['coordinate_count'] = len(coordinates)
            
            # Wykrywanie wielu wzorów przez analizę przeskoków
            patterns = self._detect_multiple_patterns(coordinates)
            stitch_data['patterns_detected'] = len(patterns)
            
            if len(patterns) > 1:
                stitch_data['multi_pattern_warning'] = True
                stitch_data['pattern_analysis'] = []
                
                for i, pattern in enumerate(patterns):
                    pattern_info = self._analyze_single_pattern(pattern, i)
                    stitch_data['pattern_analysis'].append(pattern_info)
                
                # Obliczamy łączne wymiary wszystkich wzorów
                all_x = [c[0] for c in coordinates]
                all_y = [c[1] for c in coordinates]
                stitch_data['total_dimensions'] = {
                    'width': (max(all_x) - min(all_x)) / 100.0,  # Konwersja na cm
                    'height': (max(all_y) - min(all_y)) / 100.0,  # Konwersja na cm
                    'x_min': min(all_x) / 100.0,
                    'x_max': max(all_x) / 100.0,
                    'y_min': min(all_y) / 100.0,
                    'y_max': max(all_y) / 100.0
                }
            else:
                # Pojedynczy wzór - standardowa analiza
                stitch_data['multi_pattern_warning'] = False
                pattern_info = self._analyze_single_pattern(coordinates, 0)
                stitch_data.update(pattern_info)
        
        return stitch_data
    
    def _detect_multiple_patterns(self, coordinates: List[Tuple[int, int, int]]) -> List[List[Tuple[int, int, int]]]:
        """Wykrywa wiele wzorów na podstawie długich przeskoków i znaczników końca"""
        if not coordinates:
            return []
        
        patterns = []
        current_pattern = []
        
        # Najpierw sprawdź znaczniki końca wzoru w danych binarnych
        pattern_end_markers = self._find_pattern_end_markers()
        
        for i, (x, y, cmd) in enumerate(coordinates):
            if i == 0:
                current_pattern.append((x, y, cmd))
                continue
            
            # Sprawdź czy to komenda końca wzoru (typowe kody: 0x8003, 0x8013, 0x8023)
            if cmd in [0x8003, 0x8013, 0x8023, 0x8033] and len(current_pattern) > 10:
                current_pattern.append((x, y, cmd))
                patterns.append(current_pattern)
                current_pattern = []
                continue
            
            # Oblicz dystans od poprzedniego punktu
            prev_x, prev_y, _ = coordinates[i-1]
            distance = ((x - prev_x)**2 + (y - prev_y)**2)**0.5
            
            # Jeśli dystans > 5cm (500 jednostek), prawdopodobnie nowy wzór
            if distance > 500 and len(current_pattern) > 10:
                patterns.append(current_pattern)
                current_pattern = [(x, y, cmd)]
            else:
                current_pattern.append((x, y, cmd))
        
        # Dodaj ostatni wzór
        if current_pattern:
            patterns.append(current_pattern)
        
        # Filtruj wzory które mają mniej niż 2 punktów (ultra-agresywne wykrywanie)
        patterns = [p for p in patterns if len(p) >= 2]
        
        # Jeśli wykryto wzory przez znaczniki końca, użyj ich
        if len(patterns) > 1:
            return patterns
        
        # Fallback: wykrywanie przez grupowanie współrzędnych
        return self._detect_patterns_by_clustering(coordinates)
    
    def _find_pattern_end_markers(self) -> List[int]:
        """Znajduje pozycje znaczników końca wzoru w danych binarnych"""
        end_markers = []
        
        # Szukamy typowych znaczników końca wzoru
        markers = [
            b'\x03\x80',  # 0x8003 - koniec wzoru
            b'\x13\x80',  # 0x8013 - koniec wzoru z obcięciem
            b'\x23\x80',  # 0x8023 - koniec wzoru z przeskokiem
            b'\x33\x80',  # 0x8033 - koniec wzoru z zatrzymaniem
        ]
        
        for marker in markers:
            pos = 0
            while pos < len(self.data):
                found = self.data.find(marker, pos)
                if found == -1:
                    break
                end_markers.append(found)
                pos = found + 1
        
        return sorted(end_markers)
    
    def _detect_patterns_by_clustering(self, coordinates: List[Tuple[int, int, int]]) -> List[List[Tuple[int, int, int]]]:
        """Wykrywa wzory przez grupowanie współrzędnych"""
        if not coordinates:
            return []
        
        # Groupuj punkty według odległości od siebie
        patterns = []
        current_pattern = []
        
        for i, (x, y, cmd) in enumerate(coordinates):
            if not current_pattern:
                current_pattern.append((x, y, cmd))
                continue
            
            # Sprawdź średnią odległość od punktów w aktualnym wzorze
            distances = []
            for px, py, _ in current_pattern[-5:]:  # Ostatnie 5 punktów dla większej czułości
                dist = ((x - px)**2 + (y - py)**2)**0.5
                distances.append(dist)
            
            avg_distance = sum(distances) / len(distances) if distances else 0
            
            # Jeśli punkt jest bardzo daleko od reszty wzoru, zacznij nowy wzór (ultra-czułe wykrywanie)
            if avg_distance > 500 and len(current_pattern) > 10:  # 5cm średnia odległość, mniej punktów
                patterns.append(current_pattern)
                current_pattern = [(x, y, cmd)]
            else:
                current_pattern.append((x, y, cmd))
        
        # Dodaj ostatni wzór
        if current_pattern:
            patterns.append(current_pattern)
        
        # Filtruj wzory które mają mniej niż 2 punktów (ultra-agresywne wykrywanie)
        patterns = [p for p in patterns if len(p) >= 2]
        
        return patterns if len(patterns) > 1 else [coordinates]
    
    def _analyze_single_pattern(self, coordinates: List[Tuple[int, int, int]], pattern_index: int) -> Dict[str, Any]:
        """Analizuje pojedynczy wzór"""
        if not coordinates:
            return {}
        
        x_coords = [c[0] for c in coordinates]
        y_coords = [c[1] for c in coordinates]
        
        pattern_info = {
            'pattern_index': pattern_index,
            'stitch_count': len(coordinates),
            'dimensions': {
                'width': (max(x_coords) - min(x_coords)) / 100.0,  # w cm
                'height': (max(y_coords) - min(y_coords)) / 100.0,  # w cm
                'x_min': min(x_coords) / 100.0,
                'x_max': max(x_coords) / 100.0,
                'y_min': min(y_coords) / 100.0,
                'y_max': max(y_coords) / 100.0
            }
        }
        
        # Średnia długość ściegu (analizuj maksymalną ilość punktów)
        distances = []
        for i in range(1, min(len(coordinates), 3000)):
            x1, y1, _ = coordinates[i-1]
            x2, y2, _ = coordinates[i]
            dist = ((x2-x1)**2 + (y2-y1)**2)**0.5
            distances.append(dist)
        
        if distances:
            pattern_info['average_stitch_length'] = sum(distances) / len(distances) / 100.0  # w cm
        
        # Analiza typu ściegów na podstawie komend
        stitch_types = self._analyze_pattern_stitch_types(coordinates)
        pattern_info['stitch_analysis'] = stitch_types
        
        # Analiza gęstości ściegów
        density_info = self._analyze_pattern_density(coordinates)
        pattern_info['density_analysis'] = density_info
        
        # Sprawdź czy wzór ma rozsądne wymiary
        width = pattern_info['dimensions']['width']
        height = pattern_info['dimensions']['height']
        
        if width > 100 or height > 100:  # Ponad 100 cm
            pattern_info['dimension_warning'] = 'Bardzo duże wymiary - możliwe błędne odczytanie'
        elif width < 0.1 or height < 0.1:  # Mniej niż 1 mm
            pattern_info['dimension_warning'] = 'Bardzo małe wymiary - możliwe błędne odczytanie'
        
        # Oszacowanie czasu haftu dla tego wzoru
        if pattern_info['stitch_count'] > 0:
            # Założenie: 800 ściegów/minutę
            estimated_time = pattern_info['stitch_count'] / 800.0
            pattern_info['estimated_time'] = f"{estimated_time:.1f} min"
        
        return pattern_info
    
    def _analyze_pattern_stitch_types(self, coordinates: List[Tuple[int, int, int]]) -> Dict[str, Any]:
        """Analizuje typy ściegów dla pojedynczego wzoru"""
        if not coordinates:
            return {}
        
        command_counts = {}
        jump_commands = 0
        stitch_commands = 0
        special_commands = 0
        
        for x, y, cmd in coordinates:
            if cmd not in command_counts:
                command_counts[cmd] = 0
            command_counts[cmd] += 1
            
            # Kategoryzacja komend
            if cmd == 0x0000:  # Normalny ścieg
                stitch_commands += 1
            elif cmd in [0x0001, 0x0002, 0x0003]:  # Przeskok
                jump_commands += 1
            elif cmd >= 0x8000:  # Specjalne komendy
                special_commands += 1
        
        # Interpretacja typów ściegów
        stitch_types = []
        if stitch_commands > 0:
            stitch_types.append('Running Stitch')
        if jump_commands > len(coordinates) * 0.1:  # Więcej niż 10% przeskoków
            stitch_types.append('Jump Stitch')
        if special_commands > 0:
            stitch_types.append('Special Commands')
        
        return {
            'stitch_types': stitch_types,
            'command_distribution': {
                'normal_stitches': stitch_commands,
                'jumps': jump_commands,
                'special': special_commands
            },
            'total_commands': len(coordinates)
        }
    
    def _analyze_pattern_density(self, coordinates: List[Tuple[int, int, int]]) -> Dict[str, Any]:
        """Analizuje gęstość ściegów dla pojedynczego wzoru"""
        if len(coordinates) < 2:
            return {}
        
        # Oblicz obszar wzoru
        x_coords = [c[0] for c in coordinates]
        y_coords = [c[1] for c in coordinates]
        
        width = (max(x_coords) - min(x_coords)) / 100.0  # w cm
        height = (max(y_coords) - min(y_coords)) / 100.0  # w cm
        area = width * height  # cm²
        
        if area > 0:
            density = len(coordinates) / area  # ściegów/cm²
            
            # Interpretacja gęstości (przeliczone dla cm²)
            if density < 10:
                density_level = 'Bardzo niska'
            elif density < 50:
                density_level = 'Niska'
            elif density < 200:
                density_level = 'Średnia'
            elif density < 500:
                density_level = 'Wysoka'
            else:
                density_level = 'Bardzo wysoka'
            
            return {
                'density_value': f"{density:.1f} ściegów/cm²",
                'density_level': density_level,
                'area': f"{area:.2f} cm²",
                'recommended_density': '100-300 ściegów/cm²'
            }
        
        return {}
    
    def _extract_machine_settings(self) -> Dict[str, Any]:
        """Wyciąga ustawienia maszyny"""
        settings = {}
        
        # Szukamy znaczników ustawień maszyny
        machine_markers = [
            b'SPEED',
            b'TENSION',
            b'HOOP',
            b'NEEDLE'
        ]
        
        for marker in machine_markers:
            pos = self.data.find(marker)
            if pos != -1 and pos + 8 < len(self.data):
                try:
                    # Próbujemy wyciągnąć wartość numeryczną
                    value = struct.unpack('<I', self.data[pos+4:pos+8])[0]
                    
                    if marker == b'SPEED' and 100 <= value <= 2000:
                        settings['machine_speed'] = f"{value} spm"
                    elif marker == b'TENSION' and 1 <= value <= 100:
                        settings['thread_tension'] = f"Level {value}"
                    elif marker == b'HOOP' and 50 <= value <= 500:
                        settings['hoop_dimensions'] = f"{value / 10.0:.1f} cm"
                    elif marker == b'NEEDLE' and 1 <= value <= 15:
                        settings['needle_count'] = value
                        
                except struct.error:
                    continue
        
        return settings
    
    def _calculate_technical_specs(self) -> Dict[str, Any]:
        """Oblicza specyfikacje techniczne"""
        specs = {}
        
        # Oszacowanie czasu haftu
        if 'stitch_count' in self.header_info:
            stitch_count = self.header_info['stitch_count']
            # Założenie: 800 ściegów/minutę przy średniej prędkości
            estimated_time = stitch_count / 800.0
            specs['estimated_time'] = f"{estimated_time:.1f} min"
        
        # Złożoność wzoru
        if 'color_count' in self.header_info:
            color_count = self.header_info['color_count']
            if color_count <= 2:
                specs['complexity'] = 'Prosta'
            elif color_count <= 6:
                specs['complexity'] = 'Średnia'
            else:
                specs['complexity'] = 'Złożona'
        
        return specs