import structlog
from pathlib import Path
from .client import GeminiClient
from config.settings import settings
from memory.retriever import Retriever


logger = structlog.get_logger("generation")

class SpecGenerator:
    def __init__(self, client: GeminiClient):
        self.client = client
        self.skill_path = Path("config/skill.md")
        self.retriever = Retriever()

    def _load_skill(self) -> str:
        if self.skill_path.exists():
            return self.skill_path.read_text()
        return "No specific skills defined."

    async def generate_spec(self, user_idea: str) -> str:
        skill_content = self._load_skill()
        past_prompts = await self.retriever.search_prompts(user_idea, n_results=1)
        past_context = ""
        if past_prompts:
            past_context = "\n# Past Relevant Context\n" + "\n".join(past_prompts)
            
        system_instruction = (
            "You are an expert Systems Architect. You must generate an extremely detailed "

            "You are an expert Systems Architect. You must generate an extremely detailed "
            "software specification based on the user's idea and the provided project generation rules.\n"
            "Do NOT write any actual code. Instead, write a comprehensive markdown document that will be "
            "passed as instructions to an autonomous coding agent.\n\n"
            "The specification MUST include:\n"
            "- Project goal\n"
            "- Target users\n"
            "- Functional requirements\n"
            "- Non-functional requirements\n"
            "- Folder structure\n"
            "- Architecture\n"
            "- API design\n"
            "- Database schema\n"
            "- UI structure\n"
            "- Tech stack\n"
            "- Coding standards\n"
            "- Edge cases\n"
            "- Testing strategy\n"
            "- Deployment strategy\n"
            "- Documentation requirements\n"
        )
        
        prompt = f"""
        # Project Generation Rules (skill.md)
        {skill_content}

        # User Request
        {user_idea}
        {past_context}
        """
        
        logger.info("Generating spec from idea")
        spec = await self.client.generate_content(
            model_name=settings.gemini_model_spec,
            prompt=prompt,
            system_instruction=system_instruction
        )
        return spec
