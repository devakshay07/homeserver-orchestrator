import asyncio
import structlog
import json
import os
from pathlib import Path
from typing import Tuple

from .client import GeminiClient

logger = structlog.get_logger("coder")

class GeminiCoder:
    def __init__(self, client: GeminiClient):
        self.client = client
        self.ignore_dirs = {".git", ".venv", "__pycache__", "node_modules"}

    async def _load_skills(self, instruction: str) -> str:
        skills_dir = Path("skills")
        if not skills_dir.exists():
            return ""
            
        available_skills = [f.stem for f in skills_dir.glob("*.md")]
        if not available_skills:
            return ""
            
        prompt = f"Instruction: '{instruction[:100]}...'\nWhich of these skills apply? {', '.join(available_skills)}. Return a comma separated list of skill names only."
        try:
            response = await self.client.generate_content("gemini-1.5-flash", prompt)
            selected = [s.strip() for s in response.split(",") if s.strip() in available_skills]
        except Exception:
            selected = available_skills
            
        skills_text = []
        for s in selected:
            path = skills_dir / f"{s}.md"
            if path.exists():
                skills_text.append(path.read_text())
                
        return "\n".join(skills_text)

    def _summarize_context(self, project_dir: Path) -> str:
        """Intelligently summarizes the workspace to provide context across API calls."""
        if not project_dir.exists():
            return "Project directory is empty."
            
        tree = []
        file_contents = []
        
        for root, dirs, files in os.walk(project_dir):
            dirs[:] = [d for d in dirs if d not in self.ignore_dirs]
            rel_root = Path(root).relative_to(project_dir)
            if str(rel_root) == ".":
                tree.append(".")
            else:
                tree.append(f"/{rel_root}")
                
            for file in files:
                if file.endswith(('.pyc', '.pyo', '.so', '.db', '.sqlite')):
                    continue
                tree.append(f"  ├── {file}")
                
                # Load text content for context
                file_path = Path(root) / file
                try:
                    content = file_path.read_text(errors='ignore')
                    file_contents.append(f"--- FILE: {rel_root / file} ---\n{content}\n")
                except Exception:
                    pass
                    
        summary = "WORKSPACE TREE:\n" + "\n".join(tree) + "\n\nWORKSPACE CONTENTS:\n" + "".join(file_contents)
        return summary

    async def generate(self, project_dir: Path, instruction: str) -> Tuple[int, str, str]:
        project_dir.mkdir(parents=True, exist_ok=True)
        context = self._summarize_context(project_dir)
        skills = await self._load_skills(instruction)
        
        prompt = f"""You are an autonomous Senior Software Engineer.
Your job is to read the current project context, and output the EXACT file changes needed to fulfill the instruction.

PROJECT BEST PRACTICES (SKILLS):
{skills}

CURRENT PROJECT CONTEXT:
{context}

INSTRUCTION:
{instruction}

You must return a raw JSON object (without markdown formatting blocks like ```json) with the following schema:
{{
  "files_to_update": [
    {{
      "path": "relative/path/to/file.py",
      "content": "Full new content of the file"
    }}
  ],
  "files_to_delete": [
    "relative/path/to/delete.py"
  ]
}}
Do NOT omit code. Provide the full file content for any updated file.
"""
        logger.info("Calling Gemini Coder", project_dir=str(project_dir))
        
        try:
            response_text = await self.client.generate_content("gemini-1.5-pro", prompt) # Use pro for heavy coding
            
            # Clean potential markdown wrapping
            response_text = response_text.strip()
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.startswith("```"):
                response_text = response_text[3:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
                
            data = json.loads(response_text)
            
            # Apply changes
            for f_data in data.get("files_to_update", []):
                f_path = project_dir / f_data["path"]
                f_path.parent.mkdir(parents=True, exist_ok=True)
                f_path.write_text(f_data["content"])
                
            for f_path_str in data.get("files_to_delete", []):
                f_path = project_dir / f_path_str
                if f_path.exists():
                    f_path.unlink()
                    
            return 0, "Successfully generated and applied code.", ""
            
        except json.JSONDecodeError as e:
            logger.error("Failed to parse Gemini Coder JSON response", error=str(e), response=response_text[:200])
            return -1, "", f"JSON Parsing Error: {str(e)}"
        except Exception as e:
            logger.error("Gemini Coder failed", error=str(e))
            return -1, "", str(e)
