"""
Response Templating Module.

Provides structured response templates for consistent AI Brain output.
Ensures responses follow a predictable format for each mode.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum
import re
import json
from datetime import datetime


class ResponseSection(Enum):
    """Standard sections in templated responses."""
    GREETING = "greeting"
    SUMMARY = "summary"
    ANALYSIS = "analysis"
    RECOMMENDATIONS = "recommendations"
    WARNINGS = "warnings"
    DISCLAIMER = "disclaimer"
    ACTION_ITEMS = "action_items"


@dataclass
class TemplatedResponse:
    """Structured response with sections."""
    mode: str
    sections: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_text(self, include_headers: bool = False) -> str:
        """Convert to plain text."""
        parts = []
        for section, content in self.sections.items():
            if include_headers:
                parts.append(f"**{section.replace('_', ' ').title()}**")
            parts.append(content)
        return "\n\n".join(parts)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "mode": self.mode,
            "sections": self.sections,
            "metadata": self.metadata,
        }


class ResponseTemplates:
    """
    Templates for different response modes.
    
    Provides consistent structure for:
    - Chat responses (conversational)
    - Analysis responses (structured)
    - Parse responses (JSON)
    """
    
    # Chat mode templates
    CHAT_TEMPLATES = {
        "greeting": [
            "Great question!",
            "I'd be happy to help with that.",
            "Let me explain.",
            "That's an important topic.",
        ],
        "budget_advice": """
Based on your situation, here are my recommendations:

{recommendations}

{action_items}
""",
        "saving_tips": """
Here are some effective saving strategies:

{tips}

Remember: {key_insight}
""",
        "expense_analysis": """
Looking at your spending:

**Summary:** {summary}

**Key Observations:**
{observations}

**Suggestions:**
{suggestions}
""",
    }
    
    # Analysis mode templates
    ANALYSIS_TEMPLATES = {
        "spending_analysis": """
## Spending Analysis

**Period:** {period}
**Total Spending:** ${total:.2f}

### Category Breakdown
{category_breakdown}

### Key Insights
{insights}

### Recommendations
{recommendations}
""",
        "budget_comparison": """
## Budget vs Actual Comparison

| Category | Budget | Actual | Difference |
|----------|--------|--------|------------|
{comparison_rows}

**Overall:** {budget_status}

### Areas of Concern
{concerns}

### Positive Trends
{positives}
""",
        "trend_analysis": """
## Spending Trends

**Analysis Period:** {period}

### Monthly Trends
{monthly_trends}

### Significant Changes
{changes}

### Forecast
{forecast}
""",
    }
    
    # Parse mode templates (JSON structures)
    PARSE_TEMPLATES = {
        "transaction": {
            "merchant": "",
            "amount": 0.0,
            "category": "",
            "subcategory": "",
            "date": "",
            "payment_method": "",
            "is_recurring": False,
            "confidence": 0.0,
        },
        "budget_item": {
            "category": "",
            "allocated_amount": 0.0,
            "spent_amount": 0.0,
            "remaining": 0.0,
            "percentage_used": 0.0,
        },
    }

    @classmethod
    def get_chat_template(cls, template_name: str) -> str:
        """Get a chat mode template."""
        return cls.CHAT_TEMPLATES.get(template_name, "")
    
    @classmethod
    def get_analysis_template(cls, template_name: str) -> str:
        """Get an analysis mode template."""
        return cls.ANALYSIS_TEMPLATES.get(template_name, "")
    
    @classmethod
    def get_parse_template(cls, template_name: str) -> Dict:
        """Get a parse mode JSON template."""
        return cls.PARSE_TEMPLATES.get(template_name, {}).copy()


class ResponseFormatter:
    """
    Format AI responses into consistent structures.
    
    Takes raw AI output and structures it according to templates.
    """
    
    def __init__(self):
        self.templates = ResponseTemplates()
    
    def format_chat_response(
        self,
        raw_response: str,
        intent: Optional[str] = None,
        context: Optional[Dict] = None,
    ) -> TemplatedResponse:
        """
        Format a chat response.
        
        Args:
            raw_response: Raw AI response text
            intent: Detected user intent
            context: User context
            
        Returns:
            TemplatedResponse with sections
        """
        sections = {}
        
        # Extract or add greeting
        greeting_patterns = [
            r"^(Great question!|I'd be happy to|Let me|That's an important)",
            r"^(Based on|Looking at|Here's|Here are)",
        ]
        
        has_greeting = any(re.match(p, raw_response, re.IGNORECASE) for p in greeting_patterns)
        
        if not has_greeting:
            # Add appropriate greeting
            greetings = ResponseTemplates.CHAT_TEMPLATES["greeting"]
            if intent == "budget":
                sections["greeting"] = "I'd be happy to help with your budget."
            elif intent == "savings":
                sections["greeting"] = "Great question about saving!"
            else:
                sections["greeting"] = "Let me help you with that."
        
        # Main content
        sections["content"] = raw_response.strip()
        
        # Extract recommendations if present
        recs = self._extract_section(raw_response, 
            ["recommendations", "suggest", "you should", "consider"])
        if recs:
            sections["recommendations"] = recs
        
        # Extract warnings if present
        warnings = self._extract_section(raw_response,
            ["warning", "caution", "be careful", "watch out"])
        if warnings:
            sections["warnings"] = warnings
        
        return TemplatedResponse(
            mode="chat",
            sections=sections,
            metadata={"intent": intent},
        )
    
    def format_analysis_response(
        self,
        raw_response: str,
        analysis_type: Optional[str] = None,
        data: Optional[Dict] = None,
    ) -> TemplatedResponse:
        """
        Format an analysis response.
        
        Args:
            raw_response: Raw AI analysis
            analysis_type: Type of analysis performed
            data: Analysis data
            
        Returns:
            TemplatedResponse with structured sections
        """
        sections = {}
        
        # Summary section
        summary = self._extract_first_paragraph(raw_response)
        if summary:
            sections["summary"] = summary
        
        # Key insights
        insights = self._extract_bullet_points(raw_response, "insight")
        if insights:
            sections["insights"] = insights
        
        # Recommendations
        recs = self._extract_bullet_points(raw_response, "recommend")
        if recs:
            sections["recommendations"] = recs
        
        # Full analysis (cleaned)
        sections["analysis"] = self._clean_response(raw_response)
        
        return TemplatedResponse(
            mode="analyze",
            sections=sections,
            metadata={"analysis_type": analysis_type, "data": data},
        )
    
    def format_parse_response(
        self,
        parsed_data: Dict,
        raw_response: Optional[str] = None,
    ) -> TemplatedResponse:
        """
        Format a parse response with standardized structure.
        
        Args:
            parsed_data: Parsed transaction/budget data
            raw_response: Original AI response
            
        Returns:
            TemplatedResponse with validated parse data
        """
        # Get template and fill in values
        template = ResponseTemplates.get_parse_template("transaction")
        
        standardized = {}
        for key, default in template.items():
            if key in parsed_data:
                value = parsed_data[key]
                # Type coercion
                if isinstance(default, float) and not isinstance(value, float):
                    try:
                        value = float(str(value).replace("$", "").replace(",", ""))
                    except ValueError:
                        value = default
                elif isinstance(default, bool) and not isinstance(value, bool):
                    value = str(value).lower() in ("true", "yes", "1")
                standardized[key] = value
            else:
                standardized[key] = default
        
        # Add any extra fields from parsed_data
        for key, value in parsed_data.items():
            if key not in standardized:
                standardized[key] = value
        
        return TemplatedResponse(
            mode="parse",
            sections={"parsed_data": json.dumps(standardized, indent=2)},
            metadata={"parsed": standardized},
        )
    
    def add_disclaimer(
        self,
        response: TemplatedResponse,
        disclaimer_text: str,
    ) -> TemplatedResponse:
        """Add disclaimer to response."""
        response.sections["disclaimer"] = disclaimer_text
        return response
    
    def _extract_section(self, text: str, keywords: List[str]) -> Optional[str]:
        """Extract a section based on keywords."""
        for keyword in keywords:
            pattern = rf"(?:{keyword}[:\s]*)(.+?)(?:\n\n|$)"
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                return match.group(1).strip()
        return None
    
    def _extract_first_paragraph(self, text: str) -> str:
        """Extract first paragraph."""
        paragraphs = text.strip().split("\n\n")
        if paragraphs:
            return paragraphs[0].strip()
        return text.strip()
    
    def _extract_bullet_points(self, text: str, keyword: str) -> str:
        """Extract bullet points near a keyword."""
        # Find section with keyword
        pattern = rf"({keyword}.*?)(\n\n|$)"
        match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        
        if match:
            section = match.group(1)
            # Extract bullet points
            bullets = re.findall(r"[-•*]\s*(.+)", section)
            if bullets:
                return "\n".join(f"• {b.strip()}" for b in bullets)
        
        return ""
    
    def _clean_response(self, text: str) -> str:
        """Clean up response text."""
        # Remove multiple newlines
        text = re.sub(r"\n{3,}", "\n\n", text)
        # Remove leading/trailing whitespace
        text = text.strip()
        return text


class DisclaimerGenerator:
    """Generate appropriate disclaimers for financial content."""
    
    DISCLAIMERS = {
        "general": (
            "This information is for educational purposes only and should not be "
            "considered financial advice. Please consult a qualified financial "
            "advisor for personalized recommendations."
        ),
        "investment": (
            "Investment decisions carry risk. Past performance does not guarantee "
            "future results. Consider consulting a licensed financial advisor."
        ),
        "tax": (
            "Tax laws and regulations vary and are subject to change. This is not "
            "tax advice. Please consult a qualified tax professional."
        ),
        "debt": (
            "Debt management strategies vary based on individual circumstances. "
            "Consider speaking with a certified financial counselor."
        ),
        "low_confidence": (
            "This response has lower confidence. Please verify the information "
            "and consider seeking professional advice."
        ),
    }
    
    @classmethod
    def get_disclaimer(
        cls,
        topics: List[str] = None,
        confidence: float = 1.0,
    ) -> str:
        """
        Generate appropriate disclaimer.
        
        Args:
            topics: Financial topics in response
            confidence: AI confidence score
            
        Returns:
            Combined disclaimer text
        """
        disclaimers = []
        
        # Add topic-specific disclaimers
        if topics:
            for topic in topics:
                if topic.lower() in cls.DISCLAIMERS:
                    disclaimers.append(cls.DISCLAIMERS[topic.lower()])
        
        # Add low confidence disclaimer
        if confidence < 0.7:
            disclaimers.append(cls.DISCLAIMERS["low_confidence"])
        
        # Add general if no specific
        if not disclaimers:
            disclaimers.append(cls.DISCLAIMERS["general"])
        
        return " ".join(disclaimers)


# Main formatter instance
response_formatter = ResponseFormatter()
disclaimer_generator = DisclaimerGenerator()


def format_response(
    response: str,
    mode: str,
    parsed_data: Optional[Dict] = None,
    context: Optional[Dict] = None,
    confidence: float = 1.0,
) -> TemplatedResponse:
    """
    Format an AI response into a structured template.
    
    Args:
        response: Raw AI response
        mode: Response mode (chat, analyze, parse)
        parsed_data: Parsed data for parse mode
        context: User context
        confidence: AI confidence score
        
    Returns:
        TemplatedResponse with structured sections
    """
    if mode == "chat":
        formatted = response_formatter.format_chat_response(response, context=context)
    elif mode == "analyze":
        formatted = response_formatter.format_analysis_response(response)
    elif mode == "parse":
        formatted = response_formatter.format_parse_response(parsed_data or {}, response)
    else:
        formatted = TemplatedResponse(mode=mode, sections={"content": response})
    
    # Add disclaimer if needed
    if confidence < 0.8:
        disclaimer = disclaimer_generator.get_disclaimer(confidence=confidence)
        response_formatter.add_disclaimer(formatted, disclaimer)
    
    return formatted
