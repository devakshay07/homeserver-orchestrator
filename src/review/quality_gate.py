import structlog
from pathlib import Path
from .linter import Linter
from .static_analysis import StaticAnalyzer
from .test_runner import TestRunner
from .secret_scanner import SecretScanner
from .link_checker import LinkChecker

logger = structlog.get_logger("app")

from dataclasses import dataclass, field
from enum import Enum

class GatePolicy(str, Enum):
    BLOCK = "BLOCK"
    WARN  = "WARN"

@dataclass
class StageResult:
    name: str
    passed: bool
    policy: GatePolicy = GatePolicy.BLOCK

@dataclass
class GateReport:
    stages: list[StageResult] = field(default_factory=list)

    @property
    def hard_failed(self) -> bool:
        return any(not s.passed and s.policy == GatePolicy.BLOCK for s in self.stages)

    def summary(self) -> str:
        lines = []
        for s in self.stages:
            icon = "✅" if s.passed else ("⚠️" if s.policy == GatePolicy.WARN else "❌")
            lines.append(f"{icon} {s.name}")
        return "\n".join(lines)

class QualityGate:
    def __init__(self):
        self.linter = Linter()
        self.analyzer = StaticAnalyzer()
        self.tester = TestRunner()
        self.secret_scanner = SecretScanner()
        self.link_checker = LinkChecker()


    STAGES = [
        ("Format",          GatePolicy.WARN),
        ("Lint",            GatePolicy.BLOCK),
        ("Static Analysis", GatePolicy.WARN),
        ("Unit Tests",      GatePolicy.BLOCK),
        ("Secret Scan",     GatePolicy.BLOCK),
        ("Link Check",      GatePolicy.WARN),
    ]

    async def run_all(self, project_dir: Path) -> GateReport:
        logger.info("Starting Quality Gate", project_dir=str(project_dir))
        
        import asyncio
        image_name = f"sandbox-{project_dir.name.lower()}"
        logger.info("Building Docker sandbox", image=image_name)
        
        dockerfile = """FROM python:3.9-slim
RUN pip install --no-cache-dir pytest mypy ruff detect-secrets
WORKDIR /app
"""
        if (project_dir / "requirements.txt").exists():
            dockerfile += """COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
"""
            
        df_path = project_dir / "Dockerfile.sandbox"
        df_path.write_text(dockerfile)
        
        build_proc = await asyncio.create_subprocess_exec(
            "docker", "build", "-t", image_name, "-f", "Dockerfile.sandbox", ".",
            cwd=str(project_dir),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        try:
            stdout, stderr = await asyncio.wait_for(build_proc.communicate(), timeout=300)
            if build_proc.returncode != 0:
                logger.error("Sandbox build failed", error=stderr.decode())
                report = GateReport()
                report.stages.append(StageResult(name="Sandbox Build", passed=False, policy=GatePolicy.BLOCK))
                return report
        except asyncio.TimeoutError:
            build_proc.kill()
            logger.error("Sandbox build timed out")
            report = GateReport()
            report.stages.append(StageResult(name="Sandbox Build", passed=False, policy=GatePolicy.BLOCK))
            return report

        report = GateReport()
        runners = [
            self.linter.run_format,
            self.linter.run_check,
            self.analyzer.run,
            self.tester.run,
            self.secret_scanner.run,
            self.link_checker.run,
        ]

        for (name, policy), runner in zip(self.STAGES, runners):
            try:
                passed = await runner(project_dir)
                # some runners might return None, treat as True if no exception
                if passed is None:
                    passed = True
            except Exception as e:
                passed = False
                
            result = StageResult(name=name, passed=passed, policy=policy)
            report.stages.append(result)
            
            if not passed and policy == GatePolicy.BLOCK:
                break
                
        logger.info("Quality Gate completed", project_dir=str(project_dir))
        return report
