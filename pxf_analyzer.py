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
            # Szukamy sekcji parametrów
            for i in range(0, len(self.data) - 32):
                chunk = self.data[i:i+32]
                
                # Parametry gęstości
                if b'DENSITY' in chunk:
                    try:
                        density = struct.unpack('<f', self.data[i+8:i+12])[0]
                        if 0.1 <= density <= 20:
                            params['stitch_density'] = f"{density:.1f} mm"
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
                        params['underlay_type'] = underlay_map.get(underlay_type, 'Unknown')
                    except struct.error:
                        pass
                
                # Kompensacja
                if b'COMPENSATION' in chunk or b'PULL' in chunk:
                    try:
                        compensation = struct.unpack('<f', self.data[i+8:i+12])[0]
                        if -50 <= compensation <= 50:
                            params['pull_compensation'] = f"{compensation:.1f}%"
                    except struct.error:
                        pass
                
                # Kąt wypełnienia
                if b'ANGLE' in chunk or b'FILL_ANGLE' in chunk:
                    try:
                        angle = struct.unpack('<f', self.data[i+8:i+12])[0]
                        if -180 <= angle <= 180:
                            params['fill_angle'] = f"{angle:.0f}°"
                    except struct.error:
                        pass
        
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
        """Analizuje dane ściegów"""
        stitch_data = {}
        
        # Szukamy współrzędnych ściegów
        coordinates = []
        
        for i in range(0, len(self.data) - 6, 2):
            try:
                x = struct.unpack('<h', self.data[i:i+2])[0]
                y = struct.unpack('<h', self.data[i+2:i+4])[0]
                cmd = struct.unpack('<H', self.data[i+4:i+6])[0]
                
                if -32000 < x < 32000 and -32000 < y < 32000:
                    coordinates.append((x, y, cmd))
                    
                    if len(coordinates) >= 1000:  # Ograniczamy dla wydajności
                        break
                        
            except struct.error:
                continue
        
        if coordinates:
            stitch_data['coordinate_count'] = len(coordinates)
            
            # Obliczamy wymiary wzoru
            x_coords = [c[0] for c in coordinates]
            y_coords = [c[1] for c in coordinates]
            
            stitch_data['dimensions'] = {
                'width': (max(x_coords) - min(x_coords)) / 10.0,  # w mm
                'height': (max(y_coords) - min(y_coords)) / 10.0,  # w mm
                'x_min': min(x_coords) / 10.0,
                'x_max': max(x_coords) / 10.0,
                'y_min': min(y_coords) / 10.0,
                'y_max': max(y_coords) / 10.0
            }
            
            # Średnia długość ściegu
            distances = []
            for i in range(1, min(len(coordinates), 500)):
                x1, y1, _ = coordinates[i-1]
                x2, y2, _ = coordinates[i]
                dist = ((x2-x1)**2 + (y2-y1)**2)**0.5
                distances.append(dist)
            
            if distances:
                stitch_data['average_stitch_length'] = sum(distances) / len(distances) / 10.0  # w mm
        
        return stitch_data
    
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
                        settings['speed'] = f"{value} spm"
                    elif marker == b'TENSION' and 1 <= value <= 100:
                        settings['tension'] = f"Level {value}"
                    elif marker == b'HOOP' and 50 <= value <= 500:
                        settings['hoop_size'] = f"{value} mm"
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