from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, 
                              QLabel, QPushButton, QLineEdit, QFrame, 
                              QTextEdit, QGraphicsProxyWidget, QProgressBar,
                              QMessageBox, QGroupBox, QCheckBox, QSpinBox,
                              QComboBox, QScrollArea, QSplitter, QWidget, QFormLayout)
from PySide6.QtCore import QObject, Signal, QPointF, QThread, QTimer, Qt, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QPainter, QPen, QBrush, QColor, QPainterPath, QFont, QPixmap
import requests
import json
import math
import time
import os


class LocalModelConfig:
    """
    Configuration class for local AI models through Ollama.
    """
    
    MODEL_CATEGORIES = {
        'llama': {
            'name': 'Llama 3.2',
            'models': ['llama3.2:1b', 'llama3.2:3b', 'llama3.2', 'llama3.1:8b', 'llama3.1:70b'],
            'description': 'Meta\'s Llama models - well-balanced for general tasks',
            'color': '#4F46E5'
        },
        'deepseek': {
            'name': 'DeepSeek',
            'models': ['deepseek-r1:1.5b', 'deepseek-r1:7b', 'deepseek-r1:8b', 'deepseek-r1:14b', 'deepseek-r1:32b', 'deepseek-r1:70b', 'deepseek-v3'],
            'description': 'DeepSeek models - excellent for reasoning and analysis',
            'color': '#059669'
        },
        'qwen': {
            'name': 'Qwen 2.5',
            'models': ['qwen2.5:0.5b', 'qwen2.5:1.5b', 'qwen2.5:3b', 'qwen2.5:7b', 'qwen2.5:14b', 'qwen2.5:32b', 'qwen2.5:72b'],
            'description': 'Alibaba\'s Qwen models - strong multilingual capabilities',
            'color': '#DC2626'
        },
        'qwen_coder': {
            'name': 'Qwen 2.5 Coder',
            'models': ['qwen2.5-coder:1.5b', 'qwen2.5-coder:7b', 'qwen2.5-coder:32b'],
            'description': 'Qwen specialized for coding tasks',
            'color': '#7C3AED'
        },
        'other': {
            'name': 'Other Models',
            'models': ['phi3:3.8b', 'phi3:14b', 'gemma2:9b', 'gemma2:27b', 'mistral:7b', 'codellama:7b'],
            'description': 'Other high-quality models',
            'color': '#F59E0B'
        }
    }
    
    @classmethod
    def get_all_models(cls):
        """
        Get all available models in a flat list.
        
        Returns:
            list: All model names from all categories
        """
        all_models = []
        for category in cls.MODEL_CATEGORIES.values():
            all_models.extend(category['models'])
        return all_models
    
    @classmethod
    def get_model_info(cls, model_name):
        """
        Get category and description for a model.
        
        Args:
            model_name (str): Name of the model
        
        Returns:
            dict: Model information including category, description, and color
        """
        for cat_key, category in cls.MODEL_CATEGORIES.items():
            if model_name in category['models']:
                return {
                    'category': category['name'],
                    'description': category['description'],
                    'color': category['color']
                }
        return {
            'category': 'Unknown',
            'description': 'Custom model',
            'color': "#2B2120"
        }


class LocalAIWorker(QThread):
    """
    Enhanced worker thread for local Ollama models with comprehensive data access.
    """
    
    response_ready = Signal(str)
    error_occurred = Signal(str)
    
    def __init__(self, user_message, data_context=None, model='llama3.2', temperature=0.7):
        """
        Initialize the AI worker thread.
        
        Args:
            user_message (str): User's query
            data_context (dict): Data context for AI analysis
            model (str): Model name to use
            temperature (float): Temperature parameter for generation
        """
        super().__init__()
        self.user_message = user_message
        self.data_context = data_context
        self.model = model
        self.temperature = temperature
        self.ollama_url = "http://localhost:11434/api/generate"
        
    def run(self):
        """
        Run AI generation with comprehensive data context.
        
        Returns:
            None: Emits signals with results
        """
        try:
            system_prompt = self.build_comprehensive_system_prompt()
            
            full_prompt = f"""{system_prompt}

User Question: {self.user_message}

Answer:"""

            response = requests.post(self.ollama_url, 
                json={
                    "model": self.model,
                    "prompt": full_prompt,
                    "stream": False,
                    "options": {
                        "temperature": self.temperature,
                        "top_p": 0.9,
                        "num_ctx": 8192,
                        "num_predict": 4096,
                    }
                },
                timeout=120
            )
            
            if response.status_code == 200:
                result = response.json()
                ai_response = result.get('response', 'Sorry, I could not generate a response.')
                ai_response = ai_response.strip()
                
                ai_response = self.clean_response(ai_response)
                
                if ai_response:
                    self.response_ready.emit(ai_response)
                else:
                    self.error_occurred.emit("Empty response from AI")
            else:
                error_msg = f"Ollama returned status {response.status_code}"
                try:
                    error_detail = response.json().get('error', '')
                    if error_detail:
                        error_msg += f": {error_detail}"
                except:
                    pass
                self.error_occurred.emit(error_msg)
                
        except requests.exceptions.ConnectionError:
            self.error_occurred.emit("connection_error")
        except requests.exceptions.Timeout:
            self.error_occurred.emit("timeout_error")
        except Exception as e:
            self.error_occurred.emit(f"Unexpected error: {str(e)}")
    
    def clean_response(self, response):
        """
        Clean the response to remove thinking process and make it direct.
        
        Args:
            response (str): Raw AI response
        
        Returns:
            str: Cleaned response
        """
        thinking_indicators = [
            "Let me think about this",
            "I need to analyze",
            "Let me examine",
            "First, I'll",
            "Let me look at",
            "I should",
            "Based on my analysis"
        ]
        
        for indicator in thinking_indicators:
            if response.lower().startswith(indicator.lower()):
                sentences = response.split('.')
                for i, sentence in enumerate(sentences):
                    if not any(ind.lower() in sentence.lower() for ind in thinking_indicators):
                        response = '.'.join(sentences[i:]).strip()
                        break
        
        prefixes_to_remove = [
            "Assistant:",
            "AI:",
            "Answer:",
            "Response:"
        ]
        
        for prefix in prefixes_to_remove:
            if response.startswith(prefix):
                response = response[len(prefix):].strip()
        
        return response
    
    def build_comprehensive_system_prompt(self):
        """
        Build a comprehensive system prompt with all particle data and combinations.
        
        Returns:
            str: Complete system prompt with data context
        """
        base_prompt = """You are a particle mass spectrometry data analyst. You have access to complete particle datasets with detailed composition and combination analysis. Answer questions directly and provide specific insights based on the comprehensive data provided.

GUIDELINES:
- Use specific numbers, percentages, and patterns from the data
- Reference element combinations and particle compositions
- Provide statistical insights when relevant
- Answer questions directly based on the complete dataset
- Focus on observable patterns and quantitative findings"""

        if not self.data_context:
            return base_prompt + "\n\nSTATUS: No particle data available."
        
        data_type = self.data_context.get('type', 'unknown')
        
        if data_type == 'sample_data':
            context = self.build_single_sample_context()
        elif data_type == 'multiple_sample_data':
            context = self.build_multiple_sample_context()
        else:
            context = f"\n\nDATA: {data_type} format available."
        
        return base_prompt + context
    
    def build_single_sample_context(self):
        """
        Build comprehensive context for single sample data.
        
        Returns:
            str: Formatted single sample context
        """
        sample_name = self.data_context.get('sample_name', 'Unknown')
        particles = self.data_context.get('particle_data', [])
        isotopes = self.data_context.get('selected_isotopes', [])
        data_type_str = self.data_context.get('data_type', 'counts')
        
        element_analysis = self.get_comprehensive_element_analysis(particles)
        combination_analysis = self.get_element_combination_analysis(particles)
        statistical_summary = self.get_statistical_summary(particles)
        
        context = f"""
====================
COMPREHENSIVE DATASET ANALYSIS
====================

SAMPLE INFORMATION:
- Sample Name: {sample_name}
- Total Particles Analyzed: {len(particles):,}
- Isotopes Selected: {len(isotopes)}
- Data Type: {data_type_str}
- Coverage: Complete dataset (all particles analyzed)

{element_analysis}

{combination_analysis}

{statistical_summary}

AVAILABLE ISOTOPES:
"""
        
        if isotopes:
            for isotope in isotopes[:20]:
                context += f"• {isotope.get('label', 'Unknown')}\n"
            if len(isotopes) > 20:
                context += f"• ... and {len(isotopes) - 20} more isotopes\n"
        else:
            context += "• All detected isotopes included\n"
        
        context += "\nUse this comprehensive data to answer questions about particle composition, element distributions, combinations, and statistical patterns."
        
        return context
    
    def build_multiple_sample_context(self):
        """
        Build comprehensive context for multiple sample data.
        
        Returns:
            str: Formatted multiple sample context
        """
        sample_names = self.data_context.get('sample_names', [])
        particles = self.data_context.get('particle_data', [])
        isotopes = self.data_context.get('selected_isotopes', [])
        
        samples_data = {}
        for particle in particles:
            source_sample = particle.get('source_sample')
            if source_sample:
                if source_sample not in samples_data:
                    samples_data[source_sample] = []
                samples_data[source_sample].append(particle)
        
        context = f"""
====================
MULTI-SAMPLE DATASET ANALYSIS
====================

DATASET OVERVIEW:
- Total Samples: {len(sample_names)}
- Combined Particles: {len(particles):,}
- Isotopes Selected: {len(isotopes)}
- Coverage: Complete datasets (all particles from all samples)

SAMPLE BREAKDOWN:
"""
        
        for sample_name in sample_names:
            sample_particles = samples_data.get(sample_name, [])
            if sample_particles:
                context += f"\n📁 {sample_name}:\n"
                context += f"   • Particles: {len(sample_particles):,}\n"
                
                element_counts = {}
                for particle in sample_particles:
                    for element, value in particle.get('elements', {}).items():
                        if value > 0:
                            element_counts[element] = element_counts.get(element, 0) + 1
                
                if element_counts:
                    top_elements = sorted(element_counts.items(), key=lambda x: x[1], reverse=True)[:5]
                    context += f"   • Top Elements: "
                    context += ", ".join([f"{elem} ({count} particles)" for elem, count in top_elements])
                    context += "\n"
        
        combined_element_analysis = self.get_comprehensive_element_analysis(particles)
        combined_combination_analysis = self.get_element_combination_analysis(particles)
        
        context += f"\n{combined_element_analysis}"
        context += f"\n{combined_combination_analysis}"
        
        context += "\nCOMPARATIVE ANALYSIS:\n"
        for sample_name in sample_names:
            sample_particles = samples_data.get(sample_name, [])
            if sample_particles:
                total_elements = sum(len([e for e, v in p.get('elements', {}).items() if v > 0]) 
                                   for p in sample_particles)
                avg_elements = total_elements / len(sample_particles) if sample_particles else 0
                context += f"• {sample_name}: {avg_elements:.1f} avg elements per particle\n"
        
        context += "\nUse this comprehensive multi-sample data to compare samples, identify patterns, and analyze cross-sample relationships."
        
        return context
    
    def get_comprehensive_element_analysis(self, particles):
        """
        Get comprehensive element analysis for all particles.
        
        Args:
            particles (list): List of particle data dictionaries
        
        Returns:
            str: Formatted element analysis
        """
        if not particles:
            return "ELEMENT ANALYSIS:\n• No particles detected"
        
        element_stats = {}
        total_particles = len(particles)
        
        print(f"🔍 Analyzing ALL {total_particles:,} particles for AI context...")
        
        for particle in particles:
            elements = particle.get('elements', {})
            for element_name, value in elements.items():
                if value > 0:
                    if element_name not in element_stats:
                        element_stats[element_name] = {
                            'particles': 0,
                            'total_value': 0,
                            'values': [],
                            'max_value': 0,
                            'min_value': float('inf')
                        }
                    
                    element_stats[element_name]['particles'] += 1
                    element_stats[element_name]['total_value'] += value
                    element_stats[element_name]['values'].append(value)
                    element_stats[element_name]['max_value'] = max(element_stats[element_name]['max_value'], value)
                    element_stats[element_name]['min_value'] = min(element_stats[element_name]['min_value'], value)
        
        if not element_stats:
            return "ELEMENT ANALYSIS:\n• No elements detected in particles"
        
        sorted_elements = sorted(element_stats.items(), key=lambda x: x[1]['particles'], reverse=True)
        
        analysis = "COMPREHENSIVE ELEMENT ANALYSIS:\n"
        analysis += f"• Total Unique Elements: {len(element_stats)}\n"
        analysis += f"• Analysis Coverage: {total_particles:,} particles (100% of dataset)\n\n"
        
        analysis += "TOP ELEMENTS (by frequency):\n"
        for i, (element, stats) in enumerate(sorted_elements[:15]):
            frequency = (stats['particles'] / total_particles) * 100
            avg_value = stats['total_value'] / stats['particles']
            analysis += f"{i+1:2d}. {element}:\n"
            analysis += f"    • Found in: {stats['particles']:,} particles ({frequency:.1f}%)\n"
            analysis += f"    • Average value: {avg_value:.2f}\n"
            analysis += f"    • Range: {stats['min_value']:.2f} - {stats['max_value']:.2f}\n"
        
        if len(sorted_elements) > 15:
            analysis += f"\n... and {len(sorted_elements) - 15} more elements detected\n"
        
        return analysis
    
    def get_element_combination_analysis(self, particles):
        """
        Get comprehensive element combination analysis like in heatmap.
        
        Args:
            particles (list): List of particle data dictionaries
        
        Returns:
            str: Formatted combination analysis
        """
        if not particles:
            return "COMBINATION ANALYSIS:\n• No particles available for combination analysis"
        
        print(f"🔍 Analyzing element combinations in ALL {len(particles):,} particles...")
        
        combinations = {}
        single_element_count = 0
        multi_element_count = 0
        
        for particle in particles:
            elements_in_particle = []
            element_values = {}
            
            for element_name, value in particle.get('elements', {}).items():
                if value > 0:
                    elements_in_particle.append(element_name)
                    element_values[element_name] = value
            
            if elements_in_particle:
                if len(elements_in_particle) == 1:
                    single_element_count += 1
                else:
                    multi_element_count += 1
                
                combination_key = ', '.join(sorted(elements_in_particle))
                
                if combination_key not in combinations:
                    combinations[combination_key] = {
                        'count': 0,
                        'element_count': len(elements_in_particle),
                        'total_value': 0,
                        'avg_value': 0
                    }
                
                combinations[combination_key]['count'] += 1
                particle_total = sum(element_values.values())
                combinations[combination_key]['total_value'] += particle_total
        
        for combo_data in combinations.values():
            combo_data['avg_value'] = combo_data['total_value'] / combo_data['count']
        
        sorted_combinations = sorted(combinations.items(), key=lambda x: x[1]['count'], reverse=True)
        
        total_particles = len(particles)
        analysis = "ELEMENT COMBINATION ANALYSIS:\n"
        analysis += f"• Total Combinations Found: {len(combinations)}\n"
        analysis += f"• Single-Element Particles: {single_element_count:,} ({(single_element_count/total_particles)*100:.1f}%)\n"
        analysis += f"• Multi-Element Particles: {multi_element_count:,} ({(multi_element_count/total_particles)*100:.1f}%)\n\n"
        
        analysis += "TOP ELEMENT COMBINATIONS:\n"
        for i, (combination, data) in enumerate(sorted_combinations[:20]):
            frequency = (data['count'] / total_particles) * 100
            analysis += f"{i+1:2d}. {combination}:\n"
            analysis += f"    • Particles: {data['count']:,} ({frequency:.1f}%)\n"
            analysis += f"    • Elements in combo: {data['element_count']}\n"
            analysis += f"    • Average total value: {data['avg_value']:.2f}\n"
        
        if len(sorted_combinations) > 20:
            analysis += f"\n... and {len(sorted_combinations) - 20} more combinations detected\n"
        
        complexity_stats = {}
        for combo_data in combinations.values():
            element_count = combo_data['element_count']
            if element_count not in complexity_stats:
                complexity_stats[element_count] = 0
            complexity_stats[element_count] += combo_data['count']
        
        analysis += "\nCOMBINATION COMPLEXITY DISTRIBUTION:\n"
        for element_count in sorted(complexity_stats.keys()):
            count = complexity_stats[element_count]
            percentage = (count / total_particles) * 100
            analysis += f"• {element_count}-element combinations: {count:,} particles ({percentage:.1f}%)\n"
        
        return analysis
    
    def get_statistical_summary(self, particles):
        """
        Get statistical summary of the dataset.
        
        Args:
            particles (list): List of particle data dictionaries
        
        Returns:
            str: Formatted statistical summary
        """
        if not particles:
            return "STATISTICAL SUMMARY:\n• No particles available for analysis"
        
        total_particles = len(particles)
        
        particles_with_elements = 0
        total_element_detections = 0
        values_list = []
        
        for particle in particles:
            elements = particle.get('elements', {})
            particle_elements = 0
            particle_total_value = 0
            
            for element_name, value in elements.items():
                if value > 0:
                    particle_elements += 1
                    total_element_detections += 1
                    particle_total_value += value
                    values_list.append(value)
            
            if particle_elements > 0:
                particles_with_elements += 1
        
        avg_elements_per_particle = total_element_detections / total_particles if total_particles > 0 else 0
        detection_rate = (particles_with_elements / total_particles) * 100 if total_particles > 0 else 0
        
        summary = "STATISTICAL SUMMARY:\n"
        summary += f"• Particle Detection Rate: {particles_with_elements:,}/{total_particles:,} ({detection_rate:.1f}%)\n"
        summary += f"• Average Elements per Particle: {avg_elements_per_particle:.2f}\n"
        summary += f"• Total Element Detections: {total_element_detections:,}\n"
        
        if values_list:
            import numpy as np
            values_array = np.array(values_list)
            summary += f"• Value Statistics:\n"
            summary += f"  - Mean: {np.mean(values_array):.2f}\n"
            summary += f"  - Median: {np.median(values_array):.2f}\n"
            summary += f"  - Std Dev: {np.std(values_array):.2f}\n"
            summary += f"  - Range: {np.min(values_array):.2f} - {np.max(values_array):.2f}\n"
        
        return summary


class LocalModelStatusChecker(QThread):
    """
    Check status of local Ollama models.
    """
    
    status_ready = Signal(bool, str, list)
    
    def run(self):
        """
        Check Ollama status and retrieve available models.
        
        Returns:
            None: Emits signal with status results
        """
        try:
            response = requests.get("http://localhost:11434/api/tags", timeout=10)
            
            if response.status_code == 200:
                models_data = response.json().get('models', [])
                model_names = [model.get('name', '') for model in models_data]
                
                if model_names:
                    deepseek_models = [m for m in model_names if 'deepseek' in m.lower()]
                    qwen_models = [m for m in model_names if 'qwen' in m.lower()]
                    llama_models = [m for m in model_names if 'llama' in m.lower()]
                    
                    info_parts = []
                    if deepseek_models:
                        info_parts.append(f"{len(deepseek_models)} DeepSeek")
                    if qwen_models:
                        info_parts.append(f"{len(qwen_models)} Qwen")
                    if llama_models:
                        info_parts.append(f"{len(llama_models)} Llama")
                    
                    total_other = len(model_names) - len(deepseek_models) - len(qwen_models) - len(llama_models)
                    if total_other > 0:
                        info_parts.append(f"{total_other} others")
                    
                    info = f"Ready: {', '.join(info_parts)} ({len(model_names)} total)"
                    self.status_ready.emit(True, info, model_names)
                else:
                    self.status_ready.emit(True, "Running but no models installed", [])
            else:
                self.status_ready.emit(False, "Ollama not responding", [])
                
        except Exception:
            self.status_ready.emit(False, "Ollama not running", [])


class EnhancedLocalConfigDialog(QDialog):
    """
    Enhanced configuration dialog for local models.
    """
    
    def __init__(self, ai_node, parent_window):
        """
        Initialize configuration dialog.
        
        Args:
            ai_node: AI assistant node instance
            parent_window: Parent window widget
        """
        super().__init__(parent_window)
        self.ai_node = ai_node
        self.available_models = []
        self.setWindowTitle("AI Assistant Settings")
        self.setFixedSize(800, 700)
        self.setup_ui()
        self.refresh_models()
        
    def setup_ui(self):
        """
        Set up the user interface.
        
        Returns:
            None
        """
        self.setStyleSheet("""
            QDialog {
                background-color: #FFFFFF;
                border-radius: 12px;
            }
            QGroupBox {
                font-weight: 600;
                font-size: 14px;
                color: #374151;
                border: 1px solid #E5E7EB;
                border-radius: 8px;
                padding-top: 16px;
                margin-top: 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 8px 0 8px;
                background-color: #FFFFFF;
            }
            QComboBox, QSpinBox, QLineEdit {
                border: 1px solid #D1D5DB;
                border-radius: 6px;
                padding: 8px 12px;
                background-color: #FFFFFF;
                font-size: 14px;
                min-height: 20px;
            }
            QComboBox:focus, QSpinBox:focus, QLineEdit:focus {
                border-color: #6366F1;
                outline: none;
            }
            QPushButton {
                border-radius: 6px;
                padding: 10px 16px;
                font-size: 14px;
                font-weight: 500;
                border: 1px solid transparent;
            }
            QPushButton[primary="true"] {
                background-color: #6366F1;
                color: white;
            }
            QPushButton[primary="true"]:hover {
                background-color: #5B5BD6;
            }
            QPushButton[secondary="true"] {
                background-color: #F9FAFB;
                color: #374151;
                border-color: #D1D5DB;
            }
            QPushButton[secondary="true"]:hover {
                background-color: #F3F4F6;
            }
            QTextEdit {
                border: 1px solid #D1D5DB;
                border-radius: 6px;
                padding: 8px;
                background-color: #F9FAFB;
                font-family: 'Courier New', monospace;
                font-size: 12px;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(20)
        
        header = QLabel("AI Assistant Settings")
        header.setStyleSheet("font-size: 20px; font-weight: 700; color: #111827;")
        layout.addWidget(header)
        
        subtitle = QLabel("Configure models running locally through Ollama")
        subtitle.setStyleSheet("font-size: 14px; color: #6B7280; margin-bottom: 8px;")
        layout.addWidget(subtitle)
        
        model_group = QGroupBox("Model Selection")
        model_layout = QFormLayout(model_group)
        model_layout.setSpacing(12) 
        model_layout.setContentsMargins(8, 15, 8, 8)
        
        self.model_combo = QComboBox()
        self.model_combo.currentTextChanged.connect(self.on_model_changed)
        model_layout.addRow("Active Model:", self.model_combo)
        
        layout.addWidget(model_group)
        
        advanced_group = QGroupBox("Response Settings")
        advanced_layout = QFormLayout(advanced_group)
        advanced_layout.setSpacing(12)
        advanced_layout.setContentsMargins(8, 15, 8, 12)
        
        self.temperature_spin = QSpinBox()
        self.temperature_spin.setRange(1, 20)
        self.temperature_spin.setValue(int(self.ai_node.config.get('temperature', 0.7) * 10))
        self.temperature_spin.setSuffix(" / 20")
        advanced_layout.addRow("Creativity Level:", self.temperature_spin)
        
        layout.addWidget(advanced_group)
        
        management_group = QGroupBox("Model Management")
        management_layout = QVBoxLayout(management_group)
        management_layout.setSpacing(15) 
        management_layout.setContentsMargins(8, 15, 8, 12)  
        
        category_layout = QHBoxLayout()
        category_layout.setSpacing(10)
        
        self.category_combo = QComboBox()
        self.category_combo.addItem("All Categories", "all")
        for cat_key, category in LocalModelConfig.MODEL_CATEGORIES.items():
            self.category_combo.addItem(category['name'], cat_key)
        self.category_combo.currentTextChanged.connect(self.show_category_models)
        
        refresh_btn = QPushButton("Refresh")
        refresh_btn.setProperty("secondary", True)
        refresh_btn.clicked.connect(self.refresh_models)
        
        category_layout.addWidget(QLabel("Category:"))
        category_layout.addWidget(self.category_combo)
        category_layout.addWidget(refresh_btn)
        category_layout.addStretch()
        
        management_layout.addLayout(category_layout)
        
        self.models_text = QTextEdit()
        self.models_text.setMaximumHeight(120)
        self.models_text.setReadOnly(True)
        management_layout.addWidget(self.models_text)
        
        download_label = QLabel("""To download new models: <code>ollama pull model_name</code>
Example: <code>ollama pull deepseek-r1:7b</code> or <code>ollama pull qwen2.5:7b</code>""")
        download_label.setStyleSheet("color: #6B7280; font-size: 12px; margin-top: 8px;")
        download_label.setWordWrap(True)
        management_layout.addWidget(download_label)
        
        layout.addWidget(management_group)
        
        buttons = QHBoxLayout()
        buttons.setSpacing(12)
        
        test_btn = QPushButton("Test Connection")
        test_btn.setProperty("secondary", True)
        test_btn.clicked.connect(self.test_connection)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setProperty("secondary", True)
        cancel_btn.clicked.connect(self.reject)
        
        ok_btn = QPushButton("Save Settings")
        ok_btn.setProperty("primary", True)
        ok_btn.clicked.connect(self.accept)
        
        buttons.addWidget(test_btn)
        buttons.addStretch()
        buttons.addWidget(cancel_btn)
        buttons.addWidget(ok_btn)
        
        layout.addLayout(buttons)
    
    def refresh_models(self):
        """
        Refresh available models from Ollama.
        
        Returns:
            None
        """
        try:
            response = requests.get("http://localhost:11434/api/tags", timeout=5)
            if response.status_code == 200:
                models_data = response.json().get('models', [])
                self.available_models = [model.get('name', '') for model in models_data]
                
                current_model = self.model_combo.currentText()
                self.model_combo.clear()
                
                if self.available_models:
                    self.model_combo.addItems(sorted(self.available_models))
                    
                    if current_model in self.available_models:
                        self.model_combo.setCurrentText(current_model)
                    else:
                        preferred_defaults = ['deepseek-r1:7b', 'qwen2.5-coder:7b', 'llama3.2']
                        for default in preferred_defaults:
                            if default in self.available_models:
                                self.model_combo.setCurrentText(default)
                                break
                else:
                    self.model_combo.addItem("No models available")
                
                self.show_category_models()
                
            else:
                QMessageBox.warning(self, "Connection Error", "Cannot connect to Ollama. Is it running?")
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to refresh models: {str(e)}")
    
    def show_category_models(self):
        """
        Show models for selected category.
        
        Returns:
            None
        """
        category = self.category_combo.currentData()
        
        if category == "all":
            models_to_show = LocalModelConfig.get_all_models()
            title = "All Recommended Models"
        else:
            category_info = LocalModelConfig.MODEL_CATEGORIES.get(category, {})
            models_to_show = category_info.get('models', [])
            title = category_info.get('name', 'Models')
        
        text_lines = [f"{title}:", ""]
        
        for model in models_to_show:
            status = "✅ Installed" if model in self.available_models else "⬇️ Available for download"
            model_info = LocalModelConfig.get_model_info(model)
            text_lines.append(f"• {model} - {status}")
        
        if category != "all":
            category_info = LocalModelConfig.MODEL_CATEGORIES.get(category, {})
            if 'description' in category_info:
                text_lines.extend(["", f"ℹ️ {category_info['description']}"])
        
        self.models_text.setText("\n".join(text_lines))
    
    def on_model_changed(self):
        """
        Update model info when selection changes.
        
        Returns:
            None
        """
        model = self.model_combo.currentText()
        if model and model != "No models available":
            model_info = LocalModelConfig.get_model_info(model)
            info_text = f"📁 Category: {model_info['category']}\n💡 {model_info['description']}"
            
            if ':1.5b' in model or ':0.5b' in model:
                info_text += "\nSize: ~1-2 GB (Fast, good for basic tasks)"
            elif ':3b' in model:
                info_text += "\nSize: ~2-3 GB (Balanced performance)"
            elif ':7b' in model:
                info_text += "\nSize: ~4-5 GB (Standard performance)"
            elif ':8b' in model:
                info_text += "\nSize: ~5-6 GB (Enhanced reasoning)"
            elif ':14b' in model:
                info_text += "\nSize: ~8-10 GB (High performance)"
            elif ':32b' in model:
                info_text += "\nSize: ~20-25 GB (Excellent performance)"
            elif ':70b' in model:
                info_text += "\nSize: ~40-50 GB (Maximum performance)"
    
    def test_connection(self):
        """
        Test Ollama connection.
        
        Returns:
            None
        """
        try:
            response = requests.get("http://localhost:11434/api/tags", timeout=5)
            if response.status_code == 200:
                models = response.json().get('models', [])
                
                if models:
                    current_model = self.model_combo.currentText()
                    if current_model and current_model != "No models available":
                        test_response = requests.post("http://localhost:11434/api/generate", 
                            json={"model": current_model, "prompt": "Hello", "stream": False}, 
                            timeout=10)
                        
                        if test_response.status_code == 200:
                            QMessageBox.information(self, "Connection Test", 
                                f"Successfully connected to Ollama!\n\n"
                                f"Active model: {current_model}\n"
                                f"Total models: {len(models)}")
                        else:
                            QMessageBox.warning(self, "Connection Test", 
                                f"Ollama running but model '{current_model}' not responding")
                    else:
                        QMessageBox.information(self, "Connection Test", 
                            f"Ollama is running!\n\n📁 Available models: {len(models)}")
                else:
                    QMessageBox.warning(self, "Connection Test", 
                        "Ollama running but no models installed")
            else:
                QMessageBox.warning(self, "Connection Test", 
                    "Ollama not responding correctly")
        except:
            QMessageBox.critical(self, "Connection Test", 
                "Cannot connect to Ollama\n\nPlease start Ollama: `ollama serve`")
    
    def get_config(self):
        """
        Get configuration from dialog.
        
        Returns:
            dict: Configuration dictionary with model settings
        """
        return {
            'model': self.model_combo.currentText(),
            'temperature': self.temperature_spin.value() / 10.0,
            'auto_open': self.auto_open_check.isChecked()
        }


class EnhancedLocalChatDialog(QDialog):
    """
    Enhanced chat dialog for local models.
    """
    
    def __init__(self, ai_node, parent_window):
        """
        Initialize chat dialog.
        
        Args:
            ai_node: AI assistant node instance
            parent_window: Parent window widget
        """
        super().__init__(parent_window)
        self.ai_node = ai_node
        self.parent_window = parent_window
        self.current_data = None
        self.ai_worker = None
        self.available_models = []
        
        self.setWindowTitle("Local AI Assistant")
        self.setMinimumSize(900, 700)
        self.resize(900, 700)
        
        self.check_ollama_status()
        
        self.setup_ui()
        
    def check_ollama_status(self):
        """
        Check if Ollama is available.
        
        Returns:
            None
        """
        self.status_checker = LocalModelStatusChecker()
        self.status_checker.status_ready.connect(self.on_ollama_status_checked)
        self.status_checker.start()
    
    def on_ollama_status_checked(self, is_running, info, models):
        """
        Handle Ollama status check result.
        
        Args:
            is_running (bool): Whether Ollama is running
            info (str): Status information
            models (list): List of available models
        
        Returns:
            None
        """
        self.available_models = models
        
        if hasattr(self, 'status_indicator'):
            if is_running:
                self.status_indicator.setText(f"🤖 {info}")
                self.status_indicator.setStyleSheet("color: #10B981; font-size: 12px; font-weight: 500;")
                self.setup_banner.setVisible(False)
                self.update_model_selector()
                self.update_suggestions(self.current_data)
            else:
                self.status_indicator.setText(f"{info}")
                self.status_indicator.setStyleSheet("color: #EF4444; font-size: 12px; font-weight: 500;")
                self.show_setup_banner()
    
    def setup_ui(self):
        """
        Set up the user interface.
        
        Returns:
            None
        """
        self.setStyleSheet("""
            QDialog {
                background-color: #FFFFFF;
            }
            QFrame[class="header"] {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #F8FAFC, stop:1 #EFF6FF);
                border-bottom: 1px solid #E5E7EB;
                padding: 16px 24px;
            }
            QFrame[class="suggestions"] {
                background-color: #FFFFFF;
                border-bottom: 1px solid #F3F4F6;
                padding: 12px 24px;
            }
            QFrame[class="setup-banner"] {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #FEF3C7, stop:1 #FBBF24);
                border: 1px solid #F59E0B;
                border-radius: 8px;
                padding: 16px;
                margin: 16px 24px;
            }
            QComboBox {
                border: 1px solid #D1D5DB;
                border-radius: 6px;
                padding: 6px 10px;
                background-color: #FFFFFF;
                font-size: 12px;
                min-width: 160px;
            }
            QComboBox:focus {
                border-color: #6366F1;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox::down-arrow {
                width: 12px;
                height: 12px;
            }
            QScrollArea {
                border: none;
                background-color: #FFFFFF;
            }
            QFrame[class="input-area"] {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #FFFFFF, stop:1 #F9FAFB);
                border-top: 1px solid #E5E7EB;
                padding: 20px 24px;
            }
            QLineEdit {
                border: 1px solid #D1D5DB;
                border-radius: 8px;
                padding: 12px 16px;
                font-size: 14px;
                background-color: #FFFFFF;
            }
            QLineEdit:focus {
                border-color: #6366F1;
                outline: none;
                box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.1);
            }
            QPushButton[class="send"] {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #6366F1, stop:1 #4F46E5);
                color: white;
                border: none;
                border-radius: 8px;
                padding: 12px 20px;
                font-size: 14px;
                font-weight: 600;
                min-width: 80px;
            }
            QPushButton[class="send"]:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #5B5BD6, stop:1 #4338CA);
            }
            QPushButton[class="send"]:disabled {
                background-color: #D1D5DB;
                color: #9CA3AF;
            }
            QPushButton[class="suggestion"] {
                background-color: #F8FAFC;
                color: #374151;
                border: 1px solid #E5E7EB;
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 13px;
                margin: 2px;
            }
            QPushButton[class="suggestion"]:hover {
                background-color: #F3F4F6;
                border-color: #6366F1;
                color: #6366F1;
            }
            QPushButton[class="settings"] {
                background-color: #F3F4F6;
                border: 1px solid #D1D5DB;
                border-radius: 6px;
                font-size: 14px;
                padding: 6px 8px;
                min-width: 32px;
            }
            QPushButton[class="settings"]:hover {
                background-color: #E5E7EB;
            }
            QProgressBar {
                border: none;
                background-color: #F3F4F6;
                border-radius: 2px;
                height: 4px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #6366F1, stop:1 #8B5CF6);
                border-radius: 2px;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        self.header_frame = QFrame()
        self.header_frame.setProperty("class", "header")
        header_layout = QVBoxLayout(self.header_frame)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(8)
        
        title_layout = QHBoxLayout()
        
        title_label = QLabel("AI Assistant")
        title_label.setStyleSheet("font-size: 18px; font-weight: 700; color: #111827;")
        
        model_layout = QHBoxLayout()
        model_layout.addWidget(QLabel("Model:"))
        
        self.model_combo = QComboBox()
        self.model_combo.currentTextChanged.connect(self.on_model_changed)
        model_layout.addWidget(self.model_combo)
        
        settings_btn = QPushButton("⚙️")
        settings_btn.setProperty("class", "settings")
        settings_btn.clicked.connect(self.open_settings)
        model_layout.addWidget(settings_btn)
        
        self.status_indicator = QLabel("🔄 Checking connection...")
        self.status_indicator.setStyleSheet("color: #6B7280; font-size: 12px; font-weight: 500;")
        
        title_layout.addWidget(title_label)
        title_layout.addStretch()
        title_layout.addLayout(model_layout)
        
        context_layout = QHBoxLayout()
        self.context_label = QLabel("No data connected")
        self.context_label.setStyleSheet("font-size: 13px; color: #6B7280;")
        
        context_layout.addWidget(self.context_label)
        context_layout.addStretch()
        context_layout.addWidget(self.status_indicator)
        
        header_layout.addLayout(title_layout)
        header_layout.addLayout(context_layout)
        layout.addWidget(self.header_frame)
        
        self.setup_banner = QFrame()
        self.setup_banner.setProperty("class", "setup-banner")
        self.setup_banner.setVisible(False)
        
        banner_layout = QVBoxLayout(self.setup_banner)
        banner_layout.setSpacing(8)
        
        self.banner_title = QLabel("🚀 Local AI Setup")
        self.banner_title.setStyleSheet("font-weight: 600; color: #92400E; font-size: 14px;")
        
        self.banner_text = QLabel("""To get started with local AI models:
1. Install Ollama: https://ollama.com/download
2. Start Ollama: <code>ollama serve</code>
3. Download models: <code>ollama pull deepseek-r1:7b</code> or <code>ollama pull qwen2.5:7b</code>""")
        self.banner_text.setStyleSheet("color: #92400E; font-size: 13px; line-height: 1.4;")
        self.banner_text.setWordWrap(True)
        
        banner_layout.addWidget(self.banner_title)
        banner_layout.addWidget(self.banner_text)
        layout.addWidget(self.setup_banner)
        
        self.suggestions_frame = QFrame()
        self.suggestions_frame.setProperty("class", "suggestions")
        self.suggestions_layout = QHBoxLayout(self.suggestions_frame)
        self.suggestions_layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.suggestions_frame)
        
        self.chat_scroll = QScrollArea()
        self.chat_scroll.setWidgetResizable(True)
        self.chat_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.chat_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        self.chat_widget = QWidget()
        self.chat_layout = QVBoxLayout(self.chat_widget)
        self.chat_layout.setContentsMargins(24, 16, 24, 16)
        self.chat_layout.setSpacing(0)
        self.chat_layout.addStretch()
        
        self.chat_scroll.setWidget(self.chat_widget)
        layout.addWidget(self.chat_scroll)
        
        self.thinking_frame = QFrame()
        self.thinking_frame.setVisible(False)
        thinking_layout = QVBoxLayout(self.thinking_frame)
        thinking_layout.setContentsMargins(24, 12, 24, 12)
        
        self.thinking_label = QLabel("Assistant is thinking...")
        self.thinking_label.setStyleSheet("color: #6B7280; font-size: 13px; font-style: italic;")
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        
        thinking_layout.addWidget(self.thinking_label)
        thinking_layout.addWidget(self.progress_bar)
        layout.addWidget(self.thinking_frame)
        
        input_frame = QFrame()
        input_frame.setProperty("class", "input-area")
        input_layout = QHBoxLayout(input_frame)
        input_layout.setContentsMargins(0, 0, 0, 0)
        input_layout.setSpacing(12)
        
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Ask about your particle data analysis...")
        self.input_field.returnPressed.connect(self.send_message)
        
        self.send_button = QPushButton("Send")
        self.send_button.setProperty("class", "send")
        self.send_button.clicked.connect(self.send_message)
        
        input_layout.addWidget(self.input_field)
        input_layout.addWidget(self.send_button)
        layout.addWidget(input_frame)
        
        self.add_ai_message("""Hello! I'm your **local AI assistant** for particle analysis. I run completely on your machine for maximum privacy and performance.

- **DeepSeek** - Excellent reasoning and scientific analysis
- **Qwen 2.5** - Strong multilingual and technical capabilities
- **Llama 3.2** - Well-balanced general performance""")
        
        self.update_suggestions(None)
    
    def update_model_selector(self):
        """
        Update model selector with available models.
        
        Returns:
            None
        """
        current_model = self.model_combo.currentText()
        self.model_combo.clear()
        
        if self.available_models:
            categories = {}
            other_models = []
            
            for model in sorted(self.available_models):
                categorized = False
                for cat_key, category in LocalModelConfig.MODEL_CATEGORIES.items():
                    if any(recommended in model for recommended in category['models']):
                        if cat_key not in categories:
                            categories[cat_key] = []
                        categories[cat_key].append(model)
                        categorized = True
                        break
                
                if not categorized:
                    other_models.append(model)
            
            for cat_key in ['deepseek', 'qwen', 'llama', 'other']:
                if cat_key in categories:
                    category_info = LocalModelConfig.MODEL_CATEGORIES[cat_key]
                    for model in categories[cat_key]:
                        display_name = f"{model}"
                        self.model_combo.addItem(display_name, model)
            
            for model in other_models:
                self.model_combo.addItem(f"{model}", model)
            
            current_model = self.ai_node.config.get('model', 'deepseek-r1:7b')
            for i in range(self.model_combo.count()):
                if self.model_combo.itemData(i) == current_model:
                    self.model_combo.setCurrentIndex(i)
                    break
            else:
                preferred_defaults = ['deepseek-r1:7b', 'qwen2.5:7b', 'llama3.2']
                for default in preferred_defaults:
                    for i in range(self.model_combo.count()):
                        if self.model_combo.itemData(i) == default:
                            self.model_combo.setCurrentIndex(i)
                            break
                    else:
                        continue
                    break
        else:
            self.model_combo.addItem("No models available", "none")
    
    def on_model_changed(self):
        """
        Handle model selection change.
        
        Returns:
            None
        """
        model = self.model_combo.currentData()
        if model and model != "none":
            self.ai_node.config['model'] = model
            self.thinking_label.setText("thinking...")
    
    def open_settings(self):
        """
        Open settings dialog.
        
        Returns:
            None
        """
        dialog = EnhancedLocalConfigDialog(self.ai_node, self)
        if dialog.exec() == QDialog.Accepted:
            config = dialog.get_config()
            self.ai_node.config.update(config)
            
            if config['model'] != self.model_combo.currentData():
                for i in range(self.model_combo.count()):
                    if self.model_combo.itemData(i) == config['model']:
                        self.model_combo.setCurrentIndex(i)
                        break
            
            self.check_ollama_status()
    
    def show_setup_banner(self):
        """
        Show setup instructions.
        
        Returns:
            None
        """
        self.setup_banner.setVisible(True)
    
    def update_data_context(self, data):
        """
        Update with new data context.
        
        Args:
            data (dict): Data context dictionary
        
        Returns:
            None
        """
        self.current_data = data
        
        if data:
            summary = self.ai_node.get_data_summary()
            self.context_label.setText(f"Connected: {summary}")
            self.update_suggestions(data)
            
            data_type = data.get('type', 'unknown')
            if data_type == 'sample_data':
                sample_name = data.get('sample_name', 'Unknown')
                particle_count = len(data.get('particle_data', []))
                isotope_count = len(data.get('selected_isotopes', []))
                data_type_str = data.get('data_type', 'counts')
                
                self.add_ai_message(f"""**New Dataset Connected**

**Sample:** {sample_name}  
**{particle_count:,}** particles detected  
**{isotope_count}** isotopes selected  
**Data type:** {data_type_str}

I'm ready to analyze your particle data! What would you like to explore first?""")
                
            elif data_type == 'multiple_sample_data':
                sample_count = len(data.get('sample_names', []))
                particle_count = len(data.get('particle_data', []))
                
                self.add_ai_message(f"""🔬 **Multi-Sample Dataset Connected**

**{sample_count}** samples loaded  
**{particle_count:,}** total particles  
Ready for comparative analysis

Perfect for cross-sample comparisons! What patterns should we investigate?""")
        else:
            self.context_label.setText("No data connected")
    
    def update_suggestions(self, data):
        """
        Update suggestion buttons based on data.
        
        Args:
            data (dict): Data context dictionary
        
        Returns:
            None
        """
        for i in reversed(range(self.suggestions_layout.count())): 
            child = self.suggestions_layout.itemAt(i).widget()
            if child:
                child.setParent(None)
        
        if not self.available_models:
            return
        
        suggestions = []
        
        if data and data.get('type') == 'sample_data':
            suggestions = [
                "What elements dominate?",
                "Analyze particle composition", 
            ]
        elif data and data.get('type') == 'multiple_sample_data':
            suggestions = [
                "Compare sample differences",
                "Find common patterns",
                "Which sample is most diverse?"
            ]
        else:
            suggestions = [
                "How do I get started?",
                "What data formats work?",
                "Show analysis examples",
                "Explain the workflow"
            ]
        
        for suggestion in suggestions:
            btn = QPushButton(suggestion)
            btn.setProperty("class", "suggestion")
            btn.clicked.connect(lambda checked, text=suggestion: self.send_suggestion(text))
            self.suggestions_layout.addWidget(btn)
    
    def send_suggestion(self, suggestion):
        """
        Send a suggested question.
        
        Args:
            suggestion (str): Suggestion text
        
        Returns:
            None
        """
        clean_suggestion = suggestion
        for emoji in ['🔍', '📊', '🎯', '⚡', '📈', '🏆', '🧬', '🚀', '📋', '💡', '🔄']:
            clean_suggestion = clean_suggestion.replace(emoji, '').strip()
        
        self.input_field.setText(clean_suggestion)
        self.send_message()
    
    def send_message(self):
        """
        Send message with enhanced model handling.
        
        Returns:
            None
        """
        user_message = self.input_field.text().strip()
        if not user_message:
            return
        
        if not self.available_models:
            self.show_setup_banner()
            QMessageBox.warning(self, "No Models", 
                "Please install AI models first.\n\nExample: ollama pull deepseek-r1:7b")
            return
        
        current_model = self.model_combo.currentData()
        if not current_model or current_model == "none":
            QMessageBox.warning(self, "No Model Selected", 
                "Please select a model from the dropdown.")
            return
        
        self.input_field.setEnabled(False)
        self.send_button.setEnabled(False)
        
        self.add_user_message(user_message)
        self.input_field.clear()
        
        self.thinking_frame.setVisible(True)
        
        temperature = self.ai_node.config.get('temperature', 0.7)
        
        self.ai_worker = LocalAIWorker(
            user_message, 
            self.current_data, 
            current_model,
            temperature
        )
        self.ai_worker.response_ready.connect(self.on_ai_response)
        self.ai_worker.error_occurred.connect(self.on_ai_error)
        self.ai_worker.start()
    
    def on_ai_response(self, response):
        """
        Handle successful AI response.
        
        Args:
            response (str): AI response text
        
        Returns:
            None
        """
        self.thinking_frame.setVisible(False)
        self.add_ai_message(response)
        
        self.input_field.setEnabled(True)
        self.send_button.setEnabled(True)
        self.input_field.setFocus()
    
    def on_ai_error(self, error):
        """
        Handle AI error with helpful messages.
        
        Args:
            error (str): Error message
        
        Returns:
            None
        """
        self.thinking_frame.setVisible(False)
        
        if error == "connection_error":
            self.add_ai_message("**Connection Error**\n\nI can't connect to Ollama. Please make sure it's running:\n\n```\nollama serve\n```")
            self.show_setup_banner()
        elif error == "timeout_error":
            current_model = self.model_combo.currentData()
            self.add_ai_message(f"**Timeout**\n\nThe model `{current_model}` took too long to respond. Try:\n• A simpler question\n• A smaller model (like 7B instead of 70B)\n• Check if your system has enough RAM")
        else:
            self.add_ai_message(f"**Technical Issue**\n\n```\n{error}\n```\n\nTry refreshing the connection or selecting a different model.")
        
        self.input_field.setEnabled(True)
        self.send_button.setEnabled(True)
        self.input_field.setFocus()
    
    def add_user_message(self, message):
        """
        Add user message to chat.
        
        Args:
            message (str): User message text
        
        Returns:
            None
        """
        bubble = MessageBubble(message, is_user=True)
        self.chat_layout.insertWidget(self.chat_layout.count() - 1, bubble)
        self.scroll_to_bottom()
    
    def add_ai_message(self, message):
        """
        Add AI message to chat.
        
        Args:
            message (str): AI message text
        
        Returns:
            None
        """
        bubble = MessageBubble(message, is_user=False)
        self.chat_layout.insertWidget(self.chat_layout.count() - 1, bubble)
        self.scroll_to_bottom()
    
    def scroll_to_bottom(self):
        """
        Scroll chat to bottom.
        
        Returns:
            None
        """
        QTimer.singleShot(50, lambda: self.chat_scroll.verticalScrollBar().setValue(
            self.chat_scroll.verticalScrollBar().maximum()))


class MessageBubble(QFrame):
    """
    Custom message bubble widget with enhanced styling.
    """
    
    def __init__(self, message, is_user=False, timestamp=None):
        """
        Initialize message bubble.
        
        Args:
            message (str): Message text
            is_user (bool): Whether message is from user
            timestamp (str): Timestamp string
        """
        super().__init__()
        self.message = message
        self.is_user = is_user
        self.timestamp = timestamp or time.strftime("%H:%M")
        self.setup_ui()
        
    def setup_ui(self):
        """
        Set up the user interface.
        
        Returns:
            None
        """
        self.setContentsMargins(0, 8, 0, 8)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        
        container = QFrame()
        container_layout = QHBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        
        if self.is_user:
            container_layout.addStretch()
            
            bubble = QFrame()
            bubble.setStyleSheet("""
                QFrame {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #3B82F6, stop:1 #2563EB);
                    color: white;
                    border-radius: 18px;
                    padding: 12px 16px;
                    margin-left: 80px;
                }
            """)
            
            bubble_layout = QVBoxLayout(bubble)
            bubble_layout.setContentsMargins(12, 8, 12, 8)
            bubble_layout.setSpacing(4)
            
            time_label = QLabel(self.timestamp)
            time_label.setStyleSheet("color: rgba(255, 255, 255, 0.7); font-size: 11px;")
            bubble_layout.addWidget(time_label)
            
            message_label = QLabel(self.message)
            message_label.setWordWrap(True)
            message_label.setStyleSheet("color: white; font-size: 14px; line-height: 1.4;")
            bubble_layout.addWidget(message_label)
            
            container_layout.addWidget(bubble)
            
        else:
            bubble = QFrame()
            bubble.setStyleSheet("""
                QFrame {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #FFFFFF, stop:1 #F8FAFC);
                    color: #1F2937;
                    border: 1px solid #E5E7EB;
                    border-radius: 18px;
                    padding: 12px 16px;
                    margin-right: 80px;
                }
            """)
            
            bubble_layout = QVBoxLayout(bubble)
            bubble_layout.setContentsMargins(12, 8, 12, 8)
            bubble_layout.setSpacing(4)
            
            header = QHBoxLayout()
            header.setContentsMargins(0, 0, 0, 0)
            
            avatar = QLabel("🤖")
            avatar.setStyleSheet("""
                color: #6366F1; 
                font-size: 16px; 
                font-weight: bold;
                width: 20px;
                height: 20px;
            """)
            avatar.setFixedSize(20, 20)
            
            name_label = QLabel("Assistant")
            name_label.setStyleSheet("color: #6B7280; font-size: 12px; font-weight: 600;")
            
            time_label = QLabel(self.timestamp)
            time_label.setStyleSheet("color: #9CA3AF; font-size: 11px;")
            
            header.addWidget(avatar)
            header.addWidget(name_label)
            header.addStretch()
            header.addWidget(time_label)
            
            bubble_layout.addLayout(header)
            
            message_label = QLabel(self.message)
            message_label.setWordWrap(True)
            message_label.setOpenExternalLinks(True)
            message_label.setStyleSheet("""
                color: #1F2937; 
                font-size: 14px; 
                line-height: 1.5;
                margin-top: 4px;
            """)
            
            formatted_message = self.message
            formatted_message = formatted_message.replace('**', '<b>').replace('**', '</b>')
            formatted_message = formatted_message.replace('*', '<i>').replace('*', '</i>')
            formatted_message = formatted_message.replace('```', '<pre style="background-color: #F3F4F6; padding: 8px; border-radius: 4px; margin: 4px 0;">').replace('```', '</pre>')
            formatted_message = formatted_message.replace('`', '<code style="background-color: #F3F4F6; padding: 2px 4px; border-radius: 3px;">').replace('`', '</code>')
            formatted_message = formatted_message.replace('\n', '<br>')
            
            message_label.setText(formatted_message)
            
            bubble_layout.addWidget(message_label)
            
            container_layout.addWidget(bubble)
            container_layout.addStretch()
        
        layout.addWidget(container)


class AIAssistantNode(QObject):
    """
    Enhanced local AI Assistant workflow node.
    """
    
    position_changed = Signal(QPointF)
    configuration_changed = Signal()
    
    def __init__(self, parent_window=None):
        """
        Initialize AI assistant node.
        
        Args:
            parent_window: Parent window widget
        """
        super().__init__()
        
        self.title = "AI Data Assistant"
        self.node_type = "ai_assistant"
        self.position = QPointF(0, 0)
        self._has_input = True
        self._has_output = False
        self.input_channels = ["input"]
        self.output_channels = []
        
        self.parent_window = parent_window
        self.input_data = None
        self.chat_dialog = None
        self.config = {
            'model': 'deepseek-r1:7b',
            'temperature': 0.7,
            'auto_open': False
        }
        
    def set_position(self, pos):
        """
        Set position of the node.
        
        Args:
            pos (QPointF): New position
        
        Returns:
            None
        """
        if self.position != pos:
            self.position = pos
            self.position_changed.emit(pos)
        
    def process_data(self, input_data):
        """
        Process incoming data from connected nodes.
        
        Args:
            input_data (dict): Input data dictionary
        
        Returns:
            None
        """
        self.input_data = input_data
        data_type = input_data.get('type', 'unknown') if input_data else 'None'
        print(f"AI Assistant received data: {data_type}")
        
        if self.chat_dialog and self.chat_dialog.isVisible():
            self.chat_dialog.update_data_context(input_data)
        
        if self.config.get('auto_open', False) and input_data:
            self.open_chat_dialog()
            
        self.configuration_changed.emit()
    
    def get_data_summary(self):
        """
        Get a summary of the current data for AI context.
        
        Returns:
            str: Summary string of current data
        """
        if not self.input_data:
            return "No data connected"
            
        data_type = self.input_data.get('type', 'unknown')
        
        if data_type == 'sample_data':
            sample_name = self.input_data.get('sample_name', 'Unknown')
            particles = self.input_data.get('particle_data', [])
            isotopes = self.input_data.get('selected_isotopes', [])
            data_type_str = self.input_data.get('data_type', 'counts')
            
            return f"{sample_name} ({len(particles)} particles, {len(isotopes)} isotopes, {data_type_str})"
            
        elif data_type == 'multiple_sample_data':
            sample_names = self.input_data.get('sample_names', [])
            particles = self.input_data.get('particle_data', [])
            isotopes = self.input_data.get('selected_isotopes', [])
            
            return f"{len(sample_names)} samples ({len(particles)} particles, {len(isotopes)} isotopes)"
            
        else:
            return f"Data type: {data_type}"
    
    def configure(self, parent_window):
        """
        Open configuration or chat dialog.
        
        Args:
            parent_window: Parent window widget
        
        Returns:
            bool: True if configuration was successful
        """
        if self.input_data:
            self.open_chat_dialog()
        else:
            self.show_config_dialog()
        return True
    
    def show_config_dialog(self):
        """
        Show AI assistant configuration dialog.
        
        Returns:
            None
        """
        dialog = EnhancedLocalConfigDialog(self, self.parent_window)
        if dialog.exec() == QDialog.Accepted:
            self.config.update(dialog.get_config())
            self.configuration_changed.emit()
    
    def open_chat_dialog(self):
        """
        Open the AI chat dialog with current data context.
        
        Returns:
            None
        """
        if not self.chat_dialog:
            self.chat_dialog = EnhancedLocalChatDialog(self, self.parent_window)
        
        if self.input_data:
            self.chat_dialog.update_data_context(self.input_data)
            
        self.chat_dialog.show()
        self.chat_dialog.raise_()
        self.chat_dialog.activateWindow()


def create_ai_assistant_node(parent_window):
    """
    Helper function to create local AI Assistant node.
    
    Args:
        parent_window: Parent window widget
    
    Returns:
        AIAssistantNode: New AI assistant node instance
    """
    return AIAssistantNode(parent_window)


def show_ai_assistant_dialog(parent_window, input_data=None):
    """
    Helper function to show local AI dialog directly.
    
    Args:
        parent_window: Parent window widget
        input_data (dict): Optional input data context
    
    Returns:
        None
    """
    ai_node = AIAssistantNode(parent_window)
    if input_data:
        ai_node.process_data(input_data)
    
    dialog = EnhancedLocalChatDialog(ai_node, parent_window)
    dialog.exec()