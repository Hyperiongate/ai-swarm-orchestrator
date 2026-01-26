"""
VISUAL CONTENT GENERATOR FOR LINKEDIN POSTS
Created: January 26, 2026
Last Updated: January 26, 2026

PURPOSE:
Generate engaging visual content for LinkedIn posts including:
- AI-generated images of happy workers, teams, presenters
- Data visualization charts showing improvements
- Combined graphics with branding
- Animated content (future enhancement)

FEATURES:
- DALL-E 3 integration for realistic workplace images
- Matplotlib/Plotly for professional charts
- PIL/Pillow for image composition and branding
- Template system for consistent brand identity
- Automatic image sizing for LinkedIn (1200x627 optimal)

THEMES:
- Happy workers in PPE
- Presenters with engaged audiences
- Team collaboration scenes
- Before/after comparisons
- Data-driven success stories
- Operational improvements

AUTHOR: Jim @ Shiftwork Solutions LLC
"""

import os
import io
import base64
import json
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import requests

# Try to import image libraries
try:
    from PIL import Image, ImageDraw, ImageFont, ImageFilter
    PIL_AVAILABLE = True
except ImportError:
    print("⚠️ PIL/Pillow not available - install with: pip install Pillow --break-system-packages")
    PIL_AVAILABLE = False

try:
    import matplotlib
    matplotlib.use('Agg')  # Non-interactive backend
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    print("⚠️ Matplotlib not available - install with: pip install matplotlib --break-system-packages")
    MATPLOTLIB_AVAILABLE = False

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    print("⚠️ OpenAI not available - install with: pip install openai --break-system-packages")
    OPENAI_AVAILABLE = False


class VisualContentGenerator:
    """
    Generate engaging visual content for social media posts
    """
    
    def __init__(self):
        """Initialize the visual content generator"""
        self.openai_api_key = os.environ.get('OPENAI_API_KEY')
        self.openai_client = OpenAI(api_key=self.openai_api_key) if OPENAI_AVAILABLE and self.openai_api_key else None
        
        # LinkedIn optimal dimensions
        self.linkedin_dimensions = {
            'post': (1200, 627),      # Landscape post
            'square': (1080, 1080),   # Square post
            'story': (1080, 1920)     # Story format
        }
        
        # Shiftwork Solutions brand colors
        self.brand_colors = {
            'primary_blue': '#0066A1',
            'secondary_orange': '#FF8C42',
            'dark_gray': '#2C3E50',
            'light_gray': '#ECF0F1',
            'success_green': '#27AE60',
            'warning_red': '#E74C3C',
            'text_dark': '#34495E',
            'background': '#FFFFFF'
        }
        
        # Visual content themes
        self.themes = self._load_visual_themes()
        
        # Chart types for data visualization
        self.chart_types = [
            'improvement_bar',       # Before/after bars
            'trend_line',            # Time series improvements
            'satisfaction_gauge',    # Morale/satisfaction meter
            'cost_savings',          # Cost reduction visualization
            'productivity_growth',   # Productivity increases
            'comparison_bars'        # Comparative analysis
        ]
    
    def _load_visual_themes(self) -> Dict:
        """Load visual content theme definitions"""
        return {
            'happy_workers_ppe': {
                'name': 'Happy Workers in PPE',
                'description': 'Diverse group of smiling workers wearing safety equipment',
                'prompt_template': """Professional photograph of {num_workers} happy diverse workers in a {industry} facility.
Workers are wearing appropriate PPE (hard hats, safety vests, safety glasses).
Bright, modern facility with good lighting. Workers are smiling and engaged.
Photorealistic, corporate photography style, bright and positive atmosphere.
High resolution, professional lighting, depth of field.""",
                'industries': ['manufacturing', 'food processing', 'pharmaceutical', 'chemical plant', 'distribution center'],
                'num_workers_range': (3, 8)
            },
            
            'presenter_audience': {
                'name': 'Presenter with Engaged Audience',
                'description': 'Presenter in front of attentive hourly workers',
                'prompt_template': """Professional photograph of a presenter giving a presentation to {audience_size} engaged hourly workers.
Workers in {industry} uniforms, sitting in training room or facility meeting area.
Presenter at front with screen/whiteboard, workers paying attention and engaged.
Diverse group, positive energy, professional corporate training environment.
Photorealistic, bright lighting, modern facility.""",
                'industries': ['manufacturing', 'warehouse', 'production facility', 'plant floor'],
                'audience_size_range': (15, 30)
            },
            
            'team_collaboration': {
                'name': 'Team Collaboration',
                'description': 'Workers collaborating and problem-solving together',
                'prompt_template': """Professional photograph of {num_workers} diverse workers collaborating around a table or workstation.
Workers in {industry} environment, looking at documents/tablet, engaged in discussion.
Mix of ages and backgrounds, wearing appropriate work attire.
Positive body language, teamwork, problem-solving atmosphere.
Photorealistic, natural lighting, modern facility setting.""",
                'industries': ['manufacturing', 'production', 'operations', 'facility'],
                'num_workers_range': (3, 6)
            },
            
            'success_celebration': {
                'name': 'Success Celebration',
                'description': 'Team celebrating an achievement or milestone',
                'prompt_template': """Professional photograph of {num_workers} diverse workers celebrating a success or achievement.
Workers in {industry} setting, high-fiving, smiling, positive energy.
Some wearing PPE, facility background visible.
Genuine happiness, team achievement, milestone celebration.
Photorealistic, bright and positive lighting, corporate photography style.""",
                'industries': ['manufacturing', 'production', 'operations', 'plant'],
                'num_workers_range': (4, 10)
            },
            
            'supervisor_coaching': {
                'name': 'Supervisor Coaching',
                'description': 'Supervisor mentoring or coaching workers',
                'prompt_template': """Professional photograph of a supervisor coaching or mentoring {num_workers} workers on the floor.
{industry} environment, supervisor explaining something, workers attentive and engaged.
Positive mentoring relationship, hands-on guidance, supportive atmosphere.
Diverse group, appropriate safety equipment, modern facility.
Photorealistic, natural lighting, professional corporate photography.""",
                'industries': ['manufacturing', 'production', 'warehouse', 'facility'],
                'num_workers_range': (2, 4)
            }
        }
    
    def generate_linkedin_visual(
        self,
        content_type: str,
        theme: str,
        data: Optional[Dict] = None,
        text_overlay: Optional[str] = None,
        format_type: str = 'post'
    ) -> Dict:
        """
        Generate a complete LinkedIn visual
        
        Args:
            content_type: 'image_only', 'chart_only', 'image_with_chart', 'text_graphic'
            theme: Theme name from self.themes or chart type
            data: Data for charts (if applicable)
            text_overlay: Optional text to overlay on image
            format_type: 'post', 'square', or 'story'
        
        Returns:
            {
                'success': bool,
                'image_path': str,
                'image_base64': str,
                'dimensions': tuple,
                'format': str,
                'description': str
            }
        """
        
        if content_type == 'image_only':
            return self._generate_ai_image(theme, format_type, text_overlay)
        
        elif content_type == 'chart_only':
            return self._generate_data_chart(theme, data, format_type)
        
        elif content_type == 'image_with_chart':
            return self._generate_combined_visual(theme, data, format_type, text_overlay)
        
        elif content_type == 'text_graphic':
            return self._generate_text_graphic(text_overlay, format_type)
        
        else:
            return {
                'success': False,
                'error': f'Unknown content_type: {content_type}'
            }
    
    def _generate_ai_image(
        self,
        theme: str,
        format_type: str = 'post',
        text_overlay: Optional[str] = None
    ) -> Dict:
        """Generate AI image using DALL-E 3"""
        
        if not self.openai_client:
            return {
                'success': False,
                'error': 'OpenAI client not configured - set OPENAI_API_KEY'
            }
        
        if theme not in self.themes:
            return {
                'success': False,
                'error': f'Unknown theme: {theme}. Available: {list(self.themes.keys())}'
            }
        
        theme_config = self.themes[theme]
        
        # Build the prompt
        import random
        
        if 'num_workers_range' in theme_config:
            num_workers = random.randint(*theme_config['num_workers_range'])
        else:
            num_workers = 5
        
        if 'audience_size_range' in theme_config:
            audience_size = random.randint(*theme_config['audience_size_range'])
        else:
            audience_size = None
        
        industry = random.choice(theme_config['industries'])
        
        prompt = theme_config['prompt_template'].format(
            num_workers=num_workers,
            audience_size=audience_size if audience_size else num_workers,
            industry=industry
        )
        
        # Add format guidance
        dimensions = self.linkedin_dimensions[format_type]
        aspect = 'landscape' if dimensions[0] > dimensions[1] else 'portrait' if dimensions[1] > dimensions[0] else 'square'
        prompt += f"\n{aspect.title()} format composition."
        
        try:
            # Generate image with DALL-E 3
            response = self.openai_client.images.generate(
                model="dall-e-3",
                prompt=prompt,
                size="1792x1024" if aspect == 'landscape' else "1024x1792" if aspect == 'portrait' else "1024x1024",
                quality="hd",
                n=1
            )
            
            image_url = response.data[0].url
            
            # Download the image
            img_response = requests.get(image_url, timeout=30)
            img_response.raise_for_status()
            
            if not PIL_AVAILABLE:
                return {
                    'success': False,
                    'error': 'PIL not available to process image'
                }
            
            # Open and resize image
            image = Image.open(io.BytesIO(img_response.content))
            image = image.resize(dimensions, Image.Resampling.LANCZOS)
            
            # Add text overlay if provided
            if text_overlay:
                image = self._add_text_overlay(image, text_overlay)
            
            # Add branding
            image = self._add_branding(image)
            
            # Save image
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'linkedin_{theme}_{timestamp}.png'
            filepath = f'/tmp/{filename}'
            image.save(filepath, 'PNG', quality=95)
            
            # Convert to base64
            buffered = io.BytesIO()
            image.save(buffered, format='PNG', quality=95)
            img_base64 = base64.b64encode(buffered.getvalue()).decode()
            
            return {
                'success': True,
                'image_path': filepath,
                'image_base64': img_base64,
                'dimensions': dimensions,
                'format': format_type,
                'description': theme_config['description'],
                'prompt_used': prompt
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'Failed to generate image: {str(e)}'
            }
    
    def _generate_data_chart(
        self,
        chart_type: str,
        data: Dict,
        format_type: str = 'post'
    ) -> Dict:
        """Generate data visualization chart"""
        
        if not MATPLOTLIB_AVAILABLE:
            return {
                'success': False,
                'error': 'Matplotlib not available - install matplotlib'
            }
        
        dimensions = self.linkedin_dimensions[format_type]
        dpi = 100
        figsize = (dimensions[0] / dpi, dimensions[1] / dpi)
        
        try:
            fig, ax = plt.subplots(figsize=figsize, dpi=dpi)
            fig.patch.set_facecolor(self.brand_colors['background'])
            
            if chart_type == 'improvement_bar':
                self._create_improvement_bar_chart(ax, data)
            
            elif chart_type == 'trend_line':
                self._create_trend_line_chart(ax, data)
            
            elif chart_type == 'satisfaction_gauge':
                self._create_satisfaction_gauge(ax, data)
            
            elif chart_type == 'cost_savings':
                self._create_cost_savings_chart(ax, data)
            
            elif chart_type == 'productivity_growth':
                self._create_productivity_chart(ax, data)
            
            elif chart_type == 'comparison_bars':
                self._create_comparison_chart(ax, data)
            
            else:
                plt.close()
                return {
                    'success': False,
                    'error': f'Unknown chart_type: {chart_type}'
                }
            
            plt.tight_layout()
            
            # Save to file
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'linkedin_{chart_type}_{timestamp}.png'
            filepath = f'/tmp/{filename}'
            plt.savefig(filepath, dpi=dpi, bbox_inches='tight', facecolor=fig.get_facecolor())
            
            # Convert to base64
            buffered = io.BytesIO()
            plt.savefig(buffered, format='PNG', dpi=dpi, bbox_inches='tight', facecolor=fig.get_facecolor())
            img_base64 = base64.b64encode(buffered.getvalue()).decode()
            
            plt.close()
            
            return {
                'success': True,
                'image_path': filepath,
                'image_base64': img_base64,
                'dimensions': dimensions,
                'format': format_type,
                'chart_type': chart_type
            }
            
        except Exception as e:
            plt.close()
            return {
                'success': False,
                'error': f'Failed to generate chart: {str(e)}'
            }
    
    def _create_improvement_bar_chart(self, ax, data: Dict):
        """Create before/after improvement bar chart"""
        
        categories = data.get('categories', ['Overtime', 'Turnover', 'Satisfaction'])
        before = data.get('before', [25, 18, 65])
        after = data.get('after', [12, 8, 85])
        
        x = range(len(categories))
        width = 0.35
        
        ax.bar([i - width/2 for i in x], before, width, label='Before', 
               color=self.brand_colors['warning_red'], alpha=0.8)
        ax.bar([i + width/2 for i in x], after, width, label='After',
               color=self.brand_colors['success_green'], alpha=0.8)
        
        ax.set_ylabel('Value', fontsize=14, fontweight='bold')
        ax.set_title(data.get('title', 'Operational Improvements'), 
                     fontsize=18, fontweight='bold', pad=20)
        ax.set_xticks(x)
        ax.set_xticklabels(categories, fontsize=12)
        ax.legend(fontsize=12)
        ax.grid(axis='y', alpha=0.3)
        
        # Add value labels on bars
        for i, (b, a) in enumerate(zip(before, after)):
            ax.text(i - width/2, b + 1, str(b), ha='center', va='bottom', fontweight='bold')
            ax.text(i + width/2, a + 1, str(a), ha='center', va='bottom', fontweight='bold')
    
    def _create_trend_line_chart(self, ax, data: Dict):
        """Create trend line chart showing improvements over time"""
        
        months = data.get('months', ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun'])
        values = data.get('values', [65, 68, 72, 75, 80, 85])
        metric = data.get('metric', 'Employee Satisfaction')
        
        ax.plot(months, values, marker='o', linewidth=3, markersize=10,
                color=self.brand_colors['primary_blue'])
        ax.fill_between(months, values, alpha=0.3, color=self.brand_colors['primary_blue'])
        
        ax.set_ylabel(metric, fontsize=14, fontweight='bold')
        ax.set_title(f'{metric} Improvement Over Time', 
                     fontsize=18, fontweight='bold', pad=20)
        ax.grid(True, alpha=0.3)
        ax.set_ylim(bottom=min(values) - 10, top=max(values) + 10)
        
        # Add value labels
        for i, (m, v) in enumerate(zip(months, values)):
            ax.text(i, v + 2, f'{v}%', ha='center', fontweight='bold')
    
    def _create_satisfaction_gauge(self, ax, data: Dict):
        """Create satisfaction gauge/meter"""
        
        score = data.get('score', 85)
        metric = data.get('metric', 'Employee Satisfaction')
        
        # Create gauge using pie chart
        colors = [self.brand_colors['success_green'], self.brand_colors['light_gray']]
        sizes = [score, 100 - score]
        
        wedges, texts = ax.pie(sizes, colors=colors, startangle=90, counterclock=False)
        
        # Add center circle for donut effect
        centre_circle = plt.Circle((0, 0), 0.70, fc=self.brand_colors['background'])
        ax.add_artist(centre_circle)
        
        # Add text in center
        ax.text(0, 0, f'{score}%', ha='center', va='center', 
                fontsize=48, fontweight='bold', color=self.brand_colors['text_dark'])
        ax.text(0, -0.3, metric, ha='center', va='center',
                fontsize=16, color=self.brand_colors['text_dark'])
        
        ax.set_title(data.get('title', 'Current Performance'),
                     fontsize=18, fontweight='bold', pad=20)
    
    def _create_cost_savings_chart(self, ax, data: Dict):
        """Create cost savings visualization"""
        
        categories = data.get('categories', ['Overtime', 'Turnover', 'Absenteeism'])
        savings = data.get('savings', [125000, 85000, 45000])
        
        colors = [self.brand_colors['success_green']] * len(categories)
        bars = ax.barh(categories, savings, color=colors, alpha=0.8)
        
        ax.set_xlabel('Annual Savings ($)', fontsize=14, fontweight='bold')
        ax.set_title(data.get('title', 'Cost Reduction Impact'),
                     fontsize=18, fontweight='bold', pad=20)
        ax.grid(axis='x', alpha=0.3)
        
        # Add value labels
        for i, (cat, save) in enumerate(zip(categories, savings)):
            ax.text(save + 5000, i, f'${save:,.0f}', va='center', fontweight='bold')
    
    def _create_productivity_chart(self, ax, data: Dict):
        """Create productivity growth chart"""
        
        quarters = data.get('quarters', ['Q1', 'Q2', 'Q3', 'Q4'])
        productivity = data.get('productivity', [92, 95, 98, 102])
        baseline = 100
        
        colors = [self.brand_colors['warning_red'] if p < baseline else self.brand_colors['success_green'] 
                  for p in productivity]
        
        bars = ax.bar(quarters, productivity, color=colors, alpha=0.8)
        ax.axhline(y=baseline, color=self.brand_colors['text_dark'], 
                   linestyle='--', linewidth=2, label='Baseline')
        
        ax.set_ylabel('Productivity Index', fontsize=14, fontweight='bold')
        ax.set_title(data.get('title', 'Productivity Improvement'),
                     fontsize=18, fontweight='bold', pad=20)
        ax.legend(fontsize=12)
        ax.grid(axis='y', alpha=0.3)
        
        # Add value labels
        for i, (q, p) in enumerate(zip(quarters, productivity)):
            ax.text(i, p + 1, f'{p}%', ha='center', fontweight='bold')
    
    def _create_comparison_chart(self, ax, data: Dict):
        """Create comparative analysis chart"""
        
        facilities = data.get('facilities', ['Your Facility', 'Industry Average', 'Top Quartile'])
        scores = data.get('scores', [85, 72, 90])
        
        colors = [self.brand_colors['primary_blue'] if i == 0 else self.brand_colors['light_gray']
                  for i in range(len(facilities))]
        
        bars = ax.barh(facilities, scores, color=colors, alpha=0.8)
        
        ax.set_xlabel('Performance Score', fontsize=14, fontweight='bold')
        ax.set_title(data.get('title', 'Performance Benchmarking'),
                     fontsize=18, fontweight='bold', pad=20)
        ax.grid(axis='x', alpha=0.3)
        ax.set_xlim(0, 100)
        
        # Add value labels
        for i, (fac, score) in enumerate(zip(facilities, scores)):
            ax.text(score + 2, i, f'{score}', va='center', fontweight='bold')
    
    def _generate_combined_visual(
        self,
        theme: str,
        data: Dict,
        format_type: str = 'post',
        text_overlay: Optional[str] = None
    ) -> Dict:
        """Generate combined image + chart visual"""
        
        if not PIL_AVAILABLE:
            return {
                'success': False,
                'error': 'PIL not available for image composition'
            }
        
        # Generate AI image (half size)
        img_result = self._generate_ai_image(theme, format_type, text_overlay)
        if not img_result['success']:
            return img_result
        
        # Generate chart (half size)
        chart_type = data.get('chart_type', 'improvement_bar')
        chart_result = self._generate_data_chart(chart_type, data, format_type)
        if not chart_result['success']:
            return chart_result
        
        # Combine images side by side
        try:
            img1 = Image.open(img_result['image_path'])
            img2 = Image.open(chart_result['image_path'])
            
            dimensions = self.linkedin_dimensions[format_type]
            
            # Resize each to half width
            half_width = dimensions[0] // 2
            img1 = img1.resize((half_width, dimensions[1]), Image.Resampling.LANCZOS)
            img2 = img2.resize((half_width, dimensions[1]), Image.Resampling.LANCZOS)
            
            # Create combined image
            combined = Image.new('RGB', dimensions, self.brand_colors['background'])
            combined.paste(img1, (0, 0))
            combined.paste(img2, (half_width, 0))
            
            # Add branding
            combined = self._add_branding(combined)
            
            # Save
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'linkedin_combined_{timestamp}.png'
            filepath = f'/tmp/{filename}'
            combined.save(filepath, 'PNG', quality=95)
            
            # Convert to base64
            buffered = io.BytesIO()
            combined.save(buffered, format='PNG', quality=95)
            img_base64 = base64.b64encode(buffered.getvalue()).decode()
            
            return {
                'success': True,
                'image_path': filepath,
                'image_base64': img_base64,
                'dimensions': dimensions,
                'format': format_type,
                'type': 'combined',
                'components': {
                    'image_theme': theme,
                    'chart_type': chart_type
                }
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'Failed to combine images: {str(e)}'
            }
    
    def _generate_text_graphic(
        self,
        text: str,
        format_type: str = 'post'
    ) -> Dict:
        """Generate text-based graphic with branding"""
        
        if not PIL_AVAILABLE:
            return {
                'success': False,
                'error': 'PIL not available for text graphics'
            }
        
        dimensions = self.linkedin_dimensions[format_type]
        
        try:
            # Create image
            image = Image.new('RGB', dimensions, self.brand_colors['primary_blue'])
            draw = ImageDraw.Draw(image)
            
            # Try to load a nice font
            try:
                font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 48)
            except:
                font = ImageFont.load_default()
            
            # Calculate text position
            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            
            x = (dimensions[0] - text_width) // 2
            y = (dimensions[1] - text_height) // 2
            
            # Draw text with shadow
            draw.text((x + 3, y + 3), text, fill=self.brand_colors['dark_gray'], font=font)
            draw.text((x, y), text, fill=self.brand_colors['background'], font=font)
            
            # Add branding
            image = self._add_branding(image)
            
            # Save
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'linkedin_text_{timestamp}.png'
            filepath = f'/tmp/{filename}'
            image.save(filepath, 'PNG', quality=95)
            
            # Convert to base64
            buffered = io.BytesIO()
            image.save(buffered, format='PNG', quality=95)
            img_base64 = base64.b64encode(buffered.getvalue()).decode()
            
            return {
                'success': True,
                'image_path': filepath,
                'image_base64': img_base64,
                'dimensions': dimensions,
                'format': format_type,
                'type': 'text_graphic'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'Failed to generate text graphic: {str(e)}'
            }
    
    def _add_text_overlay(self, image: Image.Image, text: str) -> Image.Image:
        """Add text overlay to image"""
        
        draw = ImageDraw.Draw(image)
        width, height = image.size
        
        # Try to load font
        try:
            font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 36)
        except:
            font = ImageFont.load_default()
        
        # Calculate text position (bottom third)
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        
        x = (width - text_width) // 2
        y = height - text_height - 60
        
        # Draw semi-transparent background
        padding = 20
        draw.rectangle(
            [x - padding, y - padding, x + text_width + padding, y + text_height + padding],
            fill=(0, 0, 0, 128)
        )
        
        # Draw text
        draw.text((x, y), text, fill='white', font=font)
        
        return image
    
    def _add_branding(self, image: Image.Image) -> Image.Image:
        """Add Shiftwork Solutions branding to image"""
        
        draw = ImageDraw.Draw(image)
        width, height = image.size
        
        # Try to load font
        try:
            font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 20)
        except:
            font = ImageFont.load_default()
        
        # Add logo text in bottom right
        branding_text = "Shiftwork Solutions"
        bbox = draw.textbbox((0, 0), branding_text, font=font)
        text_width = bbox[2] - bbox[0]
        
        x = width - text_width - 20
        y = height - 40
        
        # Draw text with subtle background
        draw.rectangle(
            [x - 10, y - 5, x + text_width + 10, y + 25],
            fill=self.brand_colors['primary_blue']
        )
        draw.text((x, y), branding_text, fill='white', font=font)
        
        return image
    
    def get_available_themes(self) -> List[str]:
        """Get list of available visual themes"""
        return list(self.themes.keys())
    
    def get_available_chart_types(self) -> List[str]:
        """Get list of available chart types"""
        return self.chart_types
    
    def check_dependencies(self) -> Dict:
        """Check which dependencies are available"""
        return {
            'PIL': PIL_AVAILABLE,
            'Matplotlib': MATPLOTLIB_AVAILABLE,
            'OpenAI': OPENAI_AVAILABLE and self.openai_client is not None,
            'ready': PIL_AVAILABLE and MATPLOTLIB_AVAILABLE and (self.openai_client is not None)
        }


# Example usage and testing
def test_visual_generator():
    """Test the visual content generator"""
    
    generator = VisualContentGenerator()
    
    print("🎨 Visual Content Generator Status:")
    deps = generator.check_dependencies()
    for dep, available in deps.items():
        status = "✅" if available else "❌"
        print(f"  {status} {dep}")
    
    print(f"\n📋 Available themes: {', '.join(generator.get_available_themes())}")
    print(f"📊 Available charts: {', '.join(generator.get_available_chart_types())}")
    
    if deps['ready']:
        print("\n✅ Ready to generate visual content!")
    else:
        print("\n⚠️ Install missing dependencies to enable visual generation")


if __name__ == '__main__':
    test_visual_generator()


# I did no harm and this file is not truncated
