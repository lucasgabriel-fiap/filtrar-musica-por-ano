#!/usr/bin/env python3
"""
===============================================================================
                        CHRONOTUNE
                 Organizador Inteligente de Musicas por Ano
                      Versao 3.0
===============================================================================
"""

import argparse
import re
import shutil
import json
import hashlib
from pathlib import Path
from typing import Optional, Tuple, Dict, List, Set
from datetime import datetime
import requests
from mutagen import File as MutagenFile
from mutagen.easyid3 import EasyID3
from mutagen.mp4 import MP4
from mutagen.flac import FLAC
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from colorama import init, Fore, Style, Back
import sys
import os
from tqdm import tqdm
import warnings

warnings.filterwarnings("ignore")
init(autoreset=True)

# CONFIGURACOES GLOBAIS
SUPPORTED_EXTENSIONS = {".mp3", ".m4a", ".mp4", ".flac", ".wav", ".ogg", ".opus", ".wma", ".aac"}
CACHE_FILE = "music_cache.json"
CONFIG_FILE = "music_filter_config.json"
BACKUP_DIR = "backup_musicas"

# Credenciais do Spotify
# Obtenha suas credenciais em: https://developer.spotify.com/dashboard
SPOTIFY_CLIENT_ID = "seu_client_id_aqui"
SPOTIFY_CLIENT_SECRET = "seu_client_secret_aqui"

class ConfigManager:
    """Gerencia configuracoes persistentes do usuario"""
    
    def __init__(self):
        self.config_path = Path(CONFIG_FILE)
        self.config = self.load_config()
    
    def load_config(self) -> Dict:
        """Carrega configuracoes salvas"""
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass
        return {
            'last_path': None,
            'last_years': [2024, 2025],
            'auto_backup': True,
            'spotify_enabled': True
        }
    
    def save_config(self):
        """Salva configuracoes"""
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"{Fore.YELLOW}Aviso: Nao foi possivel salvar configuracoes: {e}{Style.RESET_ALL}")
    
    def get(self, key: str, default=None):
        return self.config.get(key, default)
    
    def set(self, key: str, value):
        self.config[key] = value
        self.save_config()


class EnhancedMusicIdentifier:
    """Identificador de musica com multiplas fontes"""
    
    def __init__(self, spotify_enabled: bool = True, debug: bool = True):
        self.cache = self.load_cache()
        self.spotify = None
        self.spotify_enabled = spotify_enabled
        self.debug = debug
        self.stats = {'spotify_hits': 0, 'metadata_hits': 0, 'filename_hits': 0, 'cache_hits': 0}
        
        if spotify_enabled:
            self._init_spotify()
    
    def _init_spotify(self):
        """Inicializa API do Spotify"""
        try:
            auth_manager = SpotifyClientCredentials(
                client_id=SPOTIFY_CLIENT_ID,
                client_secret=SPOTIFY_CLIENT_SECRET
            )
            self.spotify = spotipy.Spotify(
                auth_manager=auth_manager,
                requests_timeout=3,
                retries=1
            )
            self.spotify.search(q='test', type='track', limit=1)
            self.spotify_enabled = True
            print(f"{Fore.GREEN}[OK] Spotify API conectada com sucesso!{Style.RESET_ALL}")
        except Exception as e:
            print(f"{Fore.YELLOW}[AVISO] Spotify desabilitado: {str(e)[:50]}{Style.RESET_ALL}")
            self.spotify_enabled = False
    
    def load_cache(self) -> Dict:
        """Carrega cache de identificacoes"""
        if Path(CACHE_FILE).exists():
            try:
                with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                    cache = json.load(f)
                    print(f"{Fore.CYAN}[INFO] Cache carregado: {len(cache)} entradas{Style.RESET_ALL}")
                    return cache
            except:
                pass
        return {}
    
    def save_cache(self):
        """Salva cache"""
        try:
            with open(CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.cache, f, indent=2, ensure_ascii=False)
        except:
            pass
    
    def get_file_hash(self, file_path: Path) -> str:
        """Gera hash unico do arquivo"""
        try:
            hasher = hashlib.md5()
            hasher.update(str(file_path.stat().st_size).encode())
            hasher.update(file_path.name.encode())
            hasher.update(str(file_path.stat().st_mtime).encode())
            return hasher.hexdigest()
        except:
            return str(file_path)
    
    def extract_metadata(self, file_path: Path) -> Dict:
        """Extrai metadados avancados"""
        metadata = {
            'title': None,
            'artist': None,
            'album': None,
            'year': None,
            'duration': None,
            'genre': None,
            'bitrate': None
        }
        
        try:
            audio = MutagenFile(file_path)
            if audio:
                if hasattr(audio.info, 'length'):
                    metadata['duration'] = int(audio.info.length)
                if hasattr(audio.info, 'bitrate'):
                    metadata['bitrate'] = audio.info.bitrate
                
                suffix = file_path.suffix.lower()
                
                # MP3
                if suffix == '.mp3':
                    try:
                        tags = EasyID3(file_path)
                        metadata['title'] = tags.get('title', [None])[0]
                        metadata['artist'] = tags.get('artist', [None])[0]
                        metadata['album'] = tags.get('album', [None])[0]
                        metadata['genre'] = tags.get('genre', [None])[0]
                        date = tags.get('date', [None])[0]
                        if date and len(str(date)) >= 4:
                            metadata['year'] = int(str(date)[:4])
                    except:
                        pass
                
                # M4A/MP4
                elif suffix in ['.m4a', '.mp4']:
                    try:
                        tags = MP4(file_path)
                        metadata['title'] = tags.get('\xa9nam', [None])[0]
                        metadata['artist'] = tags.get('\xa9ART', [None])[0]
                        metadata['album'] = tags.get('\xa9alb', [None])[0]
                        metadata['genre'] = tags.get('\xa9gen', [None])[0]
                        date = tags.get('\xa9day', [None])[0]
                        if date and len(str(date)) >= 4:
                            metadata['year'] = int(str(date)[:4])
                    except:
                        pass
                
                # FLAC
                elif suffix == '.flac':
                    try:
                        tags = FLAC(file_path)
                        metadata['title'] = tags.get('title', [None])[0]
                        metadata['artist'] = tags.get('artist', [None])[0]
                        metadata['album'] = tags.get('album', [None])[0]
                        metadata['genre'] = tags.get('genre', [None])[0]
                        date = tags.get('date', [None])[0]
                        if date and len(str(date)) >= 4:
                            metadata['year'] = int(str(date)[:4])
                    except:
                        pass
        
        except Exception as e:
            if self.debug:
                print(f"{Fore.YELLOW}Erro ao extrair metadados de {file_path.name}: {e}{Style.RESET_ALL}")
        
        # Fallback: extrair do nome do arquivo
        if not metadata['title'] or not metadata['artist']:
            filename = file_path.stem
            filename = re.sub(r'\[.*?\]', '', filename)
            filename = re.sub(r'\(.*?(official|video|audio|lyrics|hd|hq|4k|remix|edit).*?\)', '', filename, flags=re.I)
            
            patterns = [
                r'^(.+?)\s*[-–—]\s*(.+?)$',
                r'^(.+?)\s*[|]\s*(.+?)$',
                r'^(.+?)\s*[/]\s*(.+?)$',
            ]
            
            for pattern in patterns:
                match = re.match(pattern, filename.strip())
                if match:
                    metadata['artist'] = metadata['artist'] or match.group(1).strip()
                    metadata['title'] = metadata['title'] or match.group(2).strip()
                    break
            
            if not metadata['title']:
                metadata['title'] = filename.strip()
        
        # Limpar valores
        for key in metadata:
            if metadata[key] and isinstance(metadata[key], str):
                metadata[key] = re.sub(r'\s+', ' ', metadata[key]).strip()
        
        if self.debug:
            print(f"{Fore.CYAN}Metadados: {metadata['artist']} - {metadata['title']} ({metadata['year']}){Style.RESET_ALL}")
        
        return metadata
    
    def search_spotify(self, title: str, artist: str = None) -> Optional[int]:
        """Busca no Spotify com MÚLTIPLAS estratégias ULTRA melhoradas"""
        if not self.spotify_enabled or not self.spotify:
            return None
        
        # Limpar título e artista
        clean_title = title
        clean_artist = artist if artist else ""
        
        # Remover termos problemáticos
        remove_patterns = [
            r'\(Ao Vivo\)',
            r'\(ao vivo\)',
            r'\(LIVE\)',
            r'\(Live\)',
            r'DVD.*',
            r'feat\.?.*',
            r'ft\.?.*',
            r'@\w+',
            r'\[.*?\]',
            r'Deluxe',
            r'Transcende.*',
            r'Ao Vivo.*',
        ]
        
        for pattern in remove_patterns:
            clean_title = re.sub(pattern, '', clean_title, flags=re.I)
            clean_artist = re.sub(pattern, '', clean_artist, flags=re.I)
        
        # Remover tudo depois de | ou /
        clean_title = clean_title.split('|')[0].split('/')[0].strip()
        
        clean_title = re.sub(r'\s+', ' ', clean_title).strip()
        clean_artist = re.sub(r'\s+', ' ', clean_artist).strip()
        
        if self.debug:
            print(f"{Fore.CYAN}Busca limpa: '{clean_artist}' - '{clean_title}'{Style.RESET_ALL}")
        
        # ESTRATÉGIA 1: Artista + Título limpo
        if clean_artist and clean_title:
            year = self._try_search(clean_artist, clean_title, "Estratégia 1: Artista + Título")
            if year:
                return year
        
        # ESTRATÉGIA 2: Apenas título (sem artista)
        if clean_title:
            year = self._try_search(None, clean_title, "Estratégia 2: Apenas Título")
            if year:
                return year
        
        # ESTRATÉGIA 3: Primeiro nome do artista + Título
        if clean_artist and ' ' in clean_artist:
            first_artist = clean_artist.split('&')[0].split(',')[0].strip()
            year = self._try_search(first_artist, clean_title, "Estratégia 3: Primeiro artista + Título")
            if year:
                return year
        
        # ESTRATÉGIA 4: Artista + Primeiras 3 palavras do título
        if clean_artist and len(clean_title.split()) > 3:
            short_title = ' '.join(clean_title.split()[:3])
            year = self._try_search(clean_artist, short_title, "Estratégia 4: Artista + Título curto")
            if year:
                return year
        
        # ESTRATÉGIA 5: Apenas primeiras 2 palavras do título
        if len(clean_title.split()) >= 2:
            very_short_title = ' '.join(clean_title.split()[:2])
            year = self._try_search(clean_artist if clean_artist else None, very_short_title, "Estratégia 5: Título muito curto")
            if year:
                return year
        
        if self.debug:
            print(f"{Fore.RED}✗ Spotify não encontrou em nenhuma estratégia{Style.RESET_ALL}")
        
        return None
    
    def _try_search(self, artist: Optional[str], title: str, strategy_name: str) -> Optional[int]:
        """Tenta uma busca no Spotify"""
        try:
            # Montar query
            if artist:
                query = f"{artist} {title}"
            else:
                query = title
            
            # Limpar caracteres especiais
            query = re.sub(r'[^\w\s]', ' ', query)
            query = re.sub(r'\s+', ' ', query).strip()[:100]
            
            if not query or len(query) < 3:
                return None
            
            if self.debug:
                print(f"{Fore.CYAN}{strategy_name}: '{query}'{Style.RESET_ALL}")
            
            results = self.spotify.search(q=query, type='track', limit=15)
            
            if results and results['tracks']['items']:
                best_match = None
                best_score = 0
                
                for track in results['tracks']['items']:
                    track_title = track['name'].lower()
                    track_artist = track['artists'][0]['name'].lower() if track['artists'] else ''
                    
                    # Calcular similaridade
                    title_score = self._similarity(title.lower(), track_title)
                    
                    if artist:
                        artist_score = self._similarity(artist.lower(), track_artist)
                        total_score = (title_score * 0.7) + (artist_score * 0.3)
                    else:
                        total_score = title_score
                    
                    if total_score > best_score:
                        best_score = total_score
                        best_match = track
                
                # Aceitar se similaridade > 35% (mais flexível)
                if best_match and best_score > 0.35:
                    release_date = best_match['album'].get('release_date', '')
                    if release_date and len(release_date) >= 4:
                        year = int(release_date[:4])
                        if self.debug:
                            print(f"{Fore.GREEN}✓ ENCONTRADO: {best_match['name']} ({year}) - Score: {best_score:.2f}{Style.RESET_ALL}")
                        self.stats['spotify_hits'] += 1
                        return year
        
        except Exception as e:
            if self.debug:
                print(f"{Fore.YELLOW}Erro na busca: {e}{Style.RESET_ALL}")
        
        return None
    
    def _similarity(self, s1: str, s2: str) -> float:
        """Calcula similaridade entre duas strings"""
        if not s1 or not s2:
            return 0.0
        
        s1_words = set(s1.split())
        s2_words = set(s2.split())
        
        if not s1_words or not s2_words:
            return 0.0
        
        intersection = s1_words.intersection(s2_words)
        union = s1_words.union(s2_words)
        
        return len(intersection) / len(union) if union else 0.0
    
    def identify_year(self, file_path: Path, target_years: Set[int] = None) -> Tuple[Optional[int], str, float]:
        """
        Identifica o ano de lancamento
        Retorna: (ano, fonte, confianca)
        """
        if self.debug:
            print(f"\n{Fore.MAGENTA}=== Identificando: {file_path.name} ==={Style.RESET_ALL}")
        
        try:
            # Verificar cache
            file_hash = self.get_file_hash(file_path)
            if file_hash in self.cache:
                cached = self.cache[file_hash]
                self.stats['cache_hits'] += 1
                if self.debug:
                    print(f"{Fore.GREEN}✓ Encontrado no cache: Ano {cached.get('year')}{Style.RESET_ALL}")
                return cached.get('year'), cached.get('source', 'cache'), cached.get('confidence', 0.5)
            
            # Extrair metadados
            metadata = self.extract_metadata(file_path)
            
            # Prioridade 1: Metadados com ano
            if metadata['year']:
                if self.debug:
                    print(f"{Fore.GREEN}✓ Ano encontrado nos metadados: {metadata['year']}{Style.RESET_ALL}")
                
                result = (metadata['year'], 'metadata', 0.95)
                self.stats['metadata_hits'] += 1
                self._cache_result(file_hash, result)
                return result
            
            # Prioridade 2: Spotify
            if self.spotify_enabled and metadata['title']:
                if self.debug:
                    print(f"{Fore.CYAN}Tentando Spotify...{Style.RESET_ALL}")
                
                spotify_year = self.search_spotify(metadata['title'], metadata['artist'])
                if spotify_year:
                    confidence = 0.85 if metadata['artist'] else 0.70
                    result = (spotify_year, 'spotify', confidence)
                    self._cache_result(file_hash, result)
                    return result
            
            # Prioridade 3: Ano no nome do arquivo
            year_patterns = [
                r'[^\d](20[0-2][0-9])[^\d]',
                r'^(20[0-2][0-9])[^\d]',
                r'[^\d](20[0-2][0-9])$',
            ]
            
            for pattern in year_patterns:
                match = re.search(pattern, file_path.stem)
                if match:
                    year = int(match.group(1))
                    if 2000 <= year <= 2030:
                        if self.debug:
                            print(f"{Fore.GREEN}✓ Ano encontrado no nome: {year}{Style.RESET_ALL}")
                        result = (year, 'filename', 0.60)
                        self.stats['filename_hits'] += 1
                        self._cache_result(file_hash, result)
                        return result
            
            if self.debug:
                print(f"{Fore.RED}✗ Nenhum ano identificado{Style.RESET_ALL}")
        
        except Exception as e:
            if self.debug:
                print(f"{Fore.RED}Erro: {e}{Style.RESET_ALL}")
        
        return (None, 'unknown', 0.0)
    
    def _cache_result(self, file_hash: str, result: Tuple):
        """Armazena resultado no cache - APENAS SE ENCONTROU ANO"""
        if result[0] is not None:  # Só cacheia se achou ano!
            self.cache[file_hash] = {
                'year': result[0],
                'source': result[1],
                'confidence': result[2],
                'timestamp': datetime.now().isoformat()
            }


class UltraMusicFilter:
    """Filtrador ultra inteligente de musicas"""
    
    def __init__(self, root_path: Path, target_years: Set[int], backup: bool = True, 
                 spotify_enabled: bool = True, debug: bool = True):
        self.root = root_path
        self.target_years = target_years
        self.backup_enabled = backup
        self.debug = debug
        self.identifier = EnhancedMusicIdentifier(spotify_enabled, debug)
        
        self.stats = {
            'total': 0,
            'processed': 0,
            'by_year': {year: 0 for year in target_years},
            'other_years': 0,
            'unknown': 0,
            'errors': 0,
            'moved': 0,
            'backed_up': 0
        }
        
        self._create_directories()
    
    def _create_directories(self):
        """Cria diretorios para organizacao"""
        print(f"\n{Fore.CYAN}[INFO] Criando estrutura de pastas...{Style.RESET_ALL}")
        
        created_dirs = []
        
        for year in self.target_years:
            year_dir = self.root / str(year)
            if not year_dir.exists():
                year_dir.mkdir(exist_ok=True)
                created_dirs.append(str(year))
                print(f"{Fore.GREEN}[OK] Pasta criada: {year}/{Style.RESET_ALL}")
            else:
                print(f"{Fore.YELLOW}[INFO] Pasta ja existe: {year}/{Style.RESET_ALL}")
        
        outros_dir = self.root / "outros_anos"
        if not outros_dir.exists():
            outros_dir.mkdir(exist_ok=True)
            created_dirs.append("outros_anos")
            print(f"{Fore.GREEN}[OK] Pasta criada: outros_anos/{Style.RESET_ALL}")
        else:
            print(f"{Fore.YELLOW}[INFO] Pasta ja existe: outros_anos/{Style.RESET_ALL}")
        
        nao_id_dir = self.root / "nao_identificadas"
        if not nao_id_dir.exists():
            nao_id_dir.mkdir(exist_ok=True)
            created_dirs.append("nao_identificadas")
            print(f"{Fore.GREEN}[OK] Pasta criada: nao_identificadas/{Style.RESET_ALL}")
        else:
            print(f"{Fore.YELLOW}[INFO] Pasta ja existe: nao_identificadas/{Style.RESET_ALL}")
        
        if self.backup_enabled:
            self.backup_dir = self.root / BACKUP_DIR
            if not self.backup_dir.exists():
                self.backup_dir.mkdir(exist_ok=True)
                created_dirs.append(BACKUP_DIR)
                print(f"{Fore.GREEN}[OK] Pasta criada: {BACKUP_DIR}/{Style.RESET_ALL}")
            else:
                print(f"{Fore.YELLOW}[INFO] Pasta ja existe: {BACKUP_DIR}/{Style.RESET_ALL}")
        
        if created_dirs:
            print(f"{Fore.GREEN}[OK] {len(created_dirs)} pasta(s) criada(s) com sucesso!{Style.RESET_ALL}")
        else:
            print(f"{Fore.CYAN}[INFO] Todas as pastas ja existem.{Style.RESET_ALL}")
    
    def scan_files(self) -> List[Path]:
        """Escaneia arquivos de musica"""
        files = []
        exclude_dirs = set(str(year) for year in self.target_years)
        exclude_dirs.update({'outros_anos', 'nao_identificadas', BACKUP_DIR, 'antigas', 'fora_2025'})
        
        print(f"\n{Fore.CYAN}[INFO] Escaneando: {self.root}{Style.RESET_ALL}")
        
        for file_path in self.root.rglob("*"):
            if not file_path.is_file():
                continue
            
            if file_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                continue
            
            try:
                relative_parts = file_path.relative_to(self.root).parts
                if any(part in exclude_dirs for part in relative_parts):
                    if self.debug:
                        print(f"{Fore.YELLOW}Pulando (pasta excluida): {file_path}{Style.RESET_ALL}")
                    continue
            except:
                continue
            
            files.append(file_path)
        
        return files
    
    def create_backup(self, file_path: Path) -> bool:
        """Cria backup do arquivo"""
        if not self.backup_enabled:
            return True
        
        try:
            backup_path = self.backup_dir / file_path.name
            
            if backup_path.exists():
                if backup_path.stat().st_size == file_path.stat().st_size:
                    if self.debug:
                        print(f"{Fore.YELLOW}Backup ja existe: {file_path.name}{Style.RESET_ALL}")
                    return True
            
            counter = 1
            while backup_path.exists():
                backup_path = self.backup_dir / f"{file_path.stem}_{counter}{file_path.suffix}"
                counter += 1
            
            shutil.copy2(str(file_path), str(backup_path))
            self.stats['backed_up'] += 1
            return True
        except Exception as e:
            print(f"{Fore.YELLOW}[AVISO] Erro ao criar backup de {file_path.name}: {e}{Style.RESET_ALL}")
            return False
    
    def move_file(self, file_path: Path, year: Optional[int], confidence: float) -> bool:
        """Move arquivo para pasta apropriada"""
        try:
            if self.backup_enabled:
                self.create_backup(file_path)
            
            if year in self.target_years:
                dest_dir = self.root / str(year)
                dest_name = f"pasta {year}"
            elif year and confidence >= 0.5:
                dest_dir = self.root / "outros_anos"
                dest_name = f"pasta outros_anos (ano {year})"
            else:
                dest_dir = self.root / "nao_identificadas"
                dest_name = "pasta nao_identificadas"
            
            if self.debug:
                print(f"{Fore.CYAN}Movendo para {dest_name}: {file_path.name}{Style.RESET_ALL}")
            
            dest_path = dest_dir / file_path.name
            counter = 1
            while dest_path.exists():
                dest_path = dest_dir / f"{file_path.stem}_{counter}{file_path.suffix}"
                counter += 1
            
            shutil.move(str(file_path), str(dest_path))
            self.stats['moved'] += 1
            return True
        
        except Exception as e:
            print(f"{Fore.RED}[ERRO] Nao foi possivel mover {file_path.name}: {e}{Style.RESET_ALL}")
            return False
    
    def process_file(self, file_path: Path) -> Dict:
        """Processa um arquivo"""
        try:
            year, source, confidence = self.identifier.identify_year(file_path, self.target_years)
            metadata = self.identifier.extract_metadata(file_path)
            
            self.stats['processed'] += 1
            if year in self.target_years:
                self.stats['by_year'][year] += 1
            elif year:
                self.stats['other_years'] += 1
            else:
                self.stats['unknown'] += 1
            
            return {
                'path': file_path,
                'year': year,
                'source': source,
                'confidence': confidence,
                'title': metadata.get('title', file_path.stem)[:35],
                'artist': metadata.get('artist', 'Unknown')[:25],
                'success': True
            }
        
        except Exception as e:
            self.stats['errors'] += 1
            if self.debug:
                print(f"{Fore.RED}Erro ao processar {file_path.name}: {e}{Style.RESET_ALL}")
            return {
                'path': file_path,
                'year': None,
                'source': 'error',
                'confidence': 0.0,
                'title': file_path.stem[:35],
                'artist': 'Unknown',
                'success': False,
                'error': str(e)
            }
    
    def run(self):
        """Executa o processo de filtragem"""
        self._print_header()
        
        files = self.scan_files()
        self.stats['total'] = len(files)
        
        if not files:
            print(f"{Fore.RED}[ERRO] Nenhum arquivo encontrado!{Style.RESET_ALL}\n")
            return
        
        print(f"{Fore.GREEN}[OK] Encontrados {len(files)} arquivos de musica{Style.RESET_ALL}\n")
        
        if self.backup_enabled:
            print(f"{Fore.CYAN}[INFO] Backup automatico ativado: {BACKUP_DIR}/{Style.RESET_ALL}")
        
        print(f"{Fore.CYAN}[INFO] Processando e organizando arquivos...{Style.RESET_ALL}\n")
        
        with tqdm(total=len(files), desc="Progresso", ncols=100, 
                  bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]',
                  disable=False) as pbar:
            
            for file_path in files:
                try:
                    result = self.process_file(file_path)
                    
                    if result['year'] in self.target_years:
                        year_color = Fore.GREEN if result['year'] else Fore.YELLOW
                        confidence_bar = "#" * int(result['confidence'] * 10) + "." * (10 - int(result['confidence'] * 10))
                        
                        tqdm.write(
                            f"{year_color}[{result['year']}]{Style.RESET_ALL} "
                            f"{result['title']:35} | "
                            f"{result['artist']:25} | "
                            f"{confidence_bar} | "
                            f"{result['source']:8}"
                        )
                    
                    if result['success']:
                        self.move_file(file_path, result['year'], result['confidence'])
                    
                    if self.stats['processed'] % 50 == 0:
                        self.identifier.save_cache()
                
                except KeyboardInterrupt:
                    print(f"\n{Fore.YELLOW}[AVISO] Interrompido pelo usuario{Style.RESET_ALL}")
                    break
                
                except Exception as e:
                    self.stats['errors'] += 1
                    tqdm.write(f"{Fore.RED}[ERRO] {file_path.name}: {str(e)[:50]}{Style.RESET_ALL}")
                
                pbar.update(1)
        
        self.identifier.save_cache()
        self._print_summary()
    
    def _print_header(self):
        """Imprime cabecalho"""
        years_str = ", ".join(str(y) for y in sorted(self.target_years))
        
        print(f"\n{Fore.CYAN}{'='*80}{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}    CHRONOTUNE - Organizador Inteligente de Musicas{Style.RESET_ALL}")
        print(f"{Fore.CYAN}{'='*80}{Style.RESET_ALL}\n")
        print(f"{Fore.CYAN}Pasta: {self.root}{Style.RESET_ALL}")
        print(f"{Fore.CYAN}Anos alvo: {years_str}{Style.RESET_ALL}")
    
    def _print_summary(self):
        """Imprime resumo detalhado"""
        print(f"\n{Fore.CYAN}{'='*80}{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}    RESUMO DA OPERACAO{Style.RESET_ALL}")
        print(f"{Fore.CYAN}{'='*80}{Style.RESET_ALL}\n")
        
        for year in sorted(self.target_years):
            count = self.stats['by_year'].get(year, 0)
            percentage = (count / max(self.stats['total'], 1)) * 100
            bar = "#" * int(percentage / 2)
            print(f"{Fore.GREEN}Musicas de {year}: {count:4d} {bar}{Style.RESET_ALL}")
        
        print(f"\n{Fore.YELLOW}Outros anos: {self.stats['other_years']:4d}{Style.RESET_ALL}")
        print(f"{Fore.RED}Nao identificadas: {self.stats['unknown']:4d}{Style.RESET_ALL}")
        
        if self.stats['errors'] > 0:
            print(f"{Fore.RED}Erros: {self.stats['errors']:4d}{Style.RESET_ALL}")
        
        total_identified = sum(self.stats['by_year'].values()) + self.stats['other_years']
        success_rate = (total_identified / max(self.stats['total'], 1)) * 100
        
        print(f"\n{Fore.CYAN}Taxa de identificacao: {success_rate:.1f}%{Style.RESET_ALL}")
        print(f"{Fore.CYAN}Total processado: {self.stats['total']}{Style.RESET_ALL}")
        print(f"{Fore.GREEN}Arquivos movidos: {self.stats['moved']}{Style.RESET_ALL}")
        
        if self.backup_enabled:
            print(f"{Fore.CYAN}Backups criados: {self.stats['backed_up']}{Style.RESET_ALL}")
        
        print(f"\n{Fore.MAGENTA}Fontes de identificacao:{Style.RESET_ALL}")
        print(f"  - Cache: {self.identifier.stats['cache_hits']}")
        print(f"  - Metadados: {self.identifier.stats['metadata_hits']}")
        print(f"  - Spotify: {self.identifier.stats['spotify_hits']}")
        print(f"  - Nome do arquivo: {self.identifier.stats['filename_hits']}")
        
        print(f"\n{Back.GREEN}{Fore.BLACK} Operacao concluida com sucesso! {Style.RESET_ALL}\n")


def print_banner():
    """Imprime banner inicial"""
    print(f"""
{Fore.CYAN}===============================================================================
                        CHRONOTUNE
                 Organizador Inteligente de Musicas por Ano
                      Versao 3.0
===============================================================================

{Fore.GREEN}RECURSOS:{Style.RESET_ALL}
  - Deteccao automatica da pasta de musicas
  - Selecao personalizada de anos
  - Backup automatico antes de mover arquivos
  - Sistema de cache inteligente
  - Integracao com Spotify API

{Fore.CYAN}==============================================================================={Style.RESET_ALL}
""")


def get_music_folder(config: ConfigManager) -> Path:
    """Obtem pasta de musicas"""
    print(f"\n{Fore.CYAN}{'-'*80}{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}SELECIONE A PASTA DE MUSICAS{Style.RESET_ALL}")
    print(f"{Fore.CYAN}{'-'*80}{Style.RESET_ALL}\n")
    
    current_dir = Path.cwd()
    last_path = config.get('last_path')
    
    print(f"1 - Usar pasta atual: {Fore.GREEN}{current_dir}{Style.RESET_ALL}")
    
    if last_path and Path(last_path).exists():
        print(f"2 - Usar ultima pasta: {Fore.GREEN}{last_path}{Style.RESET_ALL}")
    
    print(f"3 - Digitar caminho manualmente")
    print()
    
    while True:
        choice = input(f"{Fore.CYAN}Escolha uma opcao (1-3): {Style.RESET_ALL}").strip()
        
        if choice == '1':
            config.set('last_path', str(current_dir))
            return current_dir
        
        elif choice == '2' and last_path and Path(last_path).exists():
            return Path(last_path)
        
        elif choice == '3':
            path_input = input(f"{Fore.CYAN}Digite o caminho completo: {Style.RESET_ALL}").strip()
            path = Path(path_input)
            if path.exists() and path.is_dir():
                config.set('last_path', str(path))
                return path
            else:
                print(f"{Fore.RED}[ERRO] Pasta nao encontrada! Tente novamente.{Style.RESET_ALL}\n")
        
        else:
            print(f"{Fore.RED}[ERRO] Opcao invalida!{Style.RESET_ALL}\n")


def get_target_years(config: ConfigManager) -> Set[int]:
    """Obtem anos para filtrar"""
    print(f"\n{Fore.CYAN}{'-'*80}{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}SELECIONE OS ANOS PARA FILTRAR{Style.RESET_ALL}")
    print(f"{Fore.CYAN}{'-'*80}{Style.RESET_ALL}\n")
    
    current_year = datetime.now().year
    last_years = config.get('last_years', [2024, 2025])
    
    print(f"1 - Anos recentes: {Fore.GREEN}{current_year-1} e {current_year}{Style.RESET_ALL}")
    print(f"2 - Usar ultima selecao: {Fore.GREEN}{', '.join(map(str, last_years))}{Style.RESET_ALL}")
    print(f"3 - Selecionar intervalo de anos (ex: 2020-2025)")
    print(f"4 - Selecionar anos especificos (ex: 2020, 2023, 2025)")
    print()
    
    while True:
        choice = input(f"{Fore.CYAN}Escolha uma opcao (1-4): {Style.RESET_ALL}").strip()
        
        if choice == '1':
            years = {current_year - 1, current_year}
            config.set('last_years', list(years))
            return years
        
        elif choice == '2':
            return set(last_years)
        
        elif choice == '3':
            range_input = input(f"{Fore.CYAN}Digite o intervalo (ex: 2020-2025): {Style.RESET_ALL}").strip()
            try:
                start, end = map(int, range_input.split('-'))
                if 1950 <= start <= end <= 2030:
                    years = set(range(start, end + 1))
                    config.set('last_years', list(years))
                    return years
                else:
                    print(f"{Fore.RED}[ERRO] Intervalo invalido! Use anos entre 1950 e 2030.{Style.RESET_ALL}\n")
            except:
                print(f"{Fore.RED}[ERRO] Formato invalido! Use: AAAA-AAAA{Style.RESET_ALL}\n")
        
        elif choice == '4':
            years_input = input(f"{Fore.CYAN}Digite os anos separados por virgula: {Style.RESET_ALL}").strip()
            try:
                years = set(int(y.strip()) for y in years_input.split(','))
                if all(1950 <= y <= 2030 for y in years):
                    config.set('last_years', list(years))
                    return years
                else:
                    print(f"{Fore.RED}[ERRO] Anos invalidos! Use anos entre 1950 e 2030.{Style.RESET_ALL}\n")
            except:
                print(f"{Fore.RED}[ERRO] Formato invalido! Use: AAAA, AAAA, AAAA{Style.RESET_ALL}\n")
        
        else:
            print(f"{Fore.RED}[ERRO] Opcao invalida!{Style.RESET_ALL}\n")


def get_options(config: ConfigManager) -> Dict:
    """Obtem opcoes de execucao"""
    print(f"\n{Fore.CYAN}{'-'*80}{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}OPCOES DE EXECUCAO{Style.RESET_ALL}")
    print(f"{Fore.CYAN}{'-'*80}{Style.RESET_ALL}\n")
    
    # Backup
    print(f"{Fore.CYAN}Criar backup antes de mover os arquivos?{Style.RESET_ALL}")
    print(f"  S - Sim, criar copias de seguranca (recomendado)")
    print(f"  N - Nao, apenas mover")
    backup_input = input(f"\n{Fore.CYAN}Escolha (S/N) [S]: {Style.RESET_ALL}").strip().upper()
    backup = backup_input != 'N'
    config.set('auto_backup', backup)
    
    # Spotify
    print(f"\n{Fore.CYAN}Usar Spotify para identificacao?{Style.RESET_ALL}")
    print(f"  S - Sim, usar API do Spotify (mais preciso)")
    print(f"  N - Nao, usar apenas metadados locais")
    spotify_input = input(f"\n{Fore.CYAN}Escolha (S/N) [S]: {Style.RESET_ALL}").strip().upper()
    spotify_enabled = spotify_input != 'N'
    config.set('spotify_enabled', spotify_enabled)
    
    return {
        'backup': backup,
        'spotify': spotify_enabled
    }


def confirm_execution(music_folder: Path, target_years: Set[int], options: Dict):
    """Confirma execucao"""
    print(f"\n{Fore.CYAN}{'='*80}{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}CONFIRME AS CONFIGURACOES{Style.RESET_ALL}")
    print(f"{Fore.CYAN}{'='*80}{Style.RESET_ALL}\n")
    
    print(f"{Fore.CYAN}Pasta:{Style.RESET_ALL} {music_folder}")
    print(f"{Fore.CYAN}Anos:{Style.RESET_ALL} {', '.join(map(str, sorted(target_years)))}")
    print(f"{Fore.CYAN}Backup:{Style.RESET_ALL} {'Ativado' if options['backup'] else 'Desativado'}")
    print(f"{Fore.CYAN}Spotify:{Style.RESET_ALL} {'Ativado' if options['spotify'] else 'Desativado'}")
    
    print(f"\n{Fore.YELLOW}Os arquivos serao organizados automaticamente!{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}Deseja continuar?{Style.RESET_ALL}")
    confirm = input(f"{Fore.CYAN}Digite S para continuar ou N para cancelar: {Style.RESET_ALL}").strip().upper()
    
    return confirm == 'S'


def interactive_mode():
    """Modo interativo principal"""
    print_banner()
    
    config = ConfigManager()
    
    # Perguntar sobre limpar cache
    if Path(CACHE_FILE).exists():
        print(f"\n{Fore.YELLOW}[AVISO] Cache detectado com identificacoes antigas!{Style.RESET_ALL}")
        print(f"{Fore.CYAN}Deseja limpar o cache e buscar tudo de novo?{Style.RESET_ALL}")
        print(f"  {Fore.GREEN}S{Style.RESET_ALL} - Sim, limpar cache (recomendado se houve mudancas)")
        print(f"  {Fore.YELLOW}N{Style.RESET_ALL} - Nao, usar cache existente")
        limpar = input(f"\n{Fore.CYAN}Escolha (S/N) [N]: {Style.RESET_ALL}").strip().upper()
        
        if limpar == 'S':
            try:
                Path(CACHE_FILE).unlink()
                print(f"{Fore.GREEN}[OK] Cache limpo com sucesso!{Style.RESET_ALL}")
            except Exception as e:
                print(f"{Fore.RED}[ERRO] Nao foi possivel limpar o cache: {e}{Style.RESET_ALL}")
    
    try:
        music_folder = get_music_folder(config)
        target_years = get_target_years(config)
        options = get_options(config)
        
        if not confirm_execution(music_folder, target_years, options):
            print(f"\n{Fore.YELLOW}Operacao cancelada pelo usuario.{Style.RESET_ALL}\n")
            return
        
        filter_instance = UltraMusicFilter(
            root_path=music_folder,
            target_years=target_years,
            backup=options['backup'],
            spotify_enabled=options['spotify'],
            debug=True
        )
        
        filter_instance.run()
    
    except KeyboardInterrupt:
        print(f"\n\n{Fore.YELLOW}[AVISO] Operacao cancelada pelo usuario{Style.RESET_ALL}\n")
    
    except Exception as e:
        print(f"\n{Fore.RED}[ERRO] Erro fatal: {e}{Style.RESET_ALL}\n")


def main():
    """Funcao principal"""
    
    try:
        import mutagen
        from colorama import init
        from tqdm import tqdm
        import spotipy
    except ImportError:
        print(f"{Fore.YELLOW}[INFO] Instalando dependencias necessarias...{Style.RESET_ALL}")
        os.system('pip install mutagen colorama tqdm spotipy requests')
        print(f"{Fore.GREEN}[OK] Dependencias instaladas! Execute novamente.{Style.RESET_ALL}")
        sys.exit(0)
    
    parser = argparse.ArgumentParser(
        description="ChronoTune - Organizador Inteligente de Musicas por Ano",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
MODOS DE USO:

1. MODO INTERATIVO (Recomendado):
   python chronotune.py
   
2. MODO RAPIDO:
   python chronotune.py . --years 2024,2025
   
3. MODO COMPLETO:
   python chronotune.py /home/musicas --years 2024,2025

EXEMPLOS:
  python chronotune.py
  python chronotune.py .
  python chronotune.py /home/musicas --years 2024,2025
  python chronotune.py . --years 2020-2025 --no-backup --no-spotify
        """
    )
    
    parser.add_argument('root', nargs='?', help='Pasta raiz com as musicas')
    parser.add_argument('--years', help='Anos para filtrar (ex: 2024,2025 ou 2020-2025)')
    parser.add_argument('--no-backup', action='store_true', help='Desabilitar backup automatico')
    parser.add_argument('--no-spotify', action='store_true', help='Desabilitar Spotify API')
    parser.add_argument('--interactive', action='store_true', help='Forcar modo interativo')
    parser.add_argument('--clear-cache', action='store_true', help='Limpar cache antes de executar')
    
    args = parser.parse_args()
    
    # Limpar cache se solicitado
    if args.clear_cache and Path(CACHE_FILE).exists():
        try:
            Path(CACHE_FILE).unlink()
            print(f"{Fore.GREEN}[OK] Cache limpo!{Style.RESET_ALL}")
        except:
            print(f"{Fore.RED}[ERRO] Nao foi possivel limpar cache{Style.RESET_ALL}")
    
    if not args.root or args.interactive:
        interactive_mode()
        return
    
    root_path = Path(args.root)
    if not root_path.exists():
        print(f"{Fore.RED}[ERRO] Pasta '{root_path}' nao existe!{Style.RESET_ALL}")
        sys.exit(1)
    
    if args.years:
        try:
            if '-' in args.years:
                start, end = map(int, args.years.split('-'))
                target_years = set(range(start, end + 1))
            else:
                target_years = set(int(y.strip()) for y in args.years.split(','))
        except:
            print(f"{Fore.RED}[ERRO] Formato de anos invalido!{Style.RESET_ALL}")
            sys.exit(1)
    else:
        current_year = datetime.now().year
        target_years = {current_year - 1, current_year}
    
    filter_instance = UltraMusicFilter(
        root_path=root_path,
        target_years=target_years,
        backup=not args.no_backup,
        spotify_enabled=not args.no_spotify,
        debug=True
    )
    
    try:
        filter_instance.run()
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}[AVISO] Operacao cancelada{Style.RESET_ALL}")
        sys.exit(0)


if __name__ == "__main__":
    main()
