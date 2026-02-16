from collections.abc import Iterable

from pydantic import BaseModel, Field


class SkillManifest(BaseModel):
    name: str
    version: str
    enabled: bool = True
    requirements: list[str] = Field(default_factory=list)
    operation_capabilities: dict[str, str]


class SkillRegistry:
    def __init__(self, manifests: Iterable[SkillManifest]) -> None:
        self._by_name = {manifest.name: manifest for manifest in manifests}

    def list(self) -> list[SkillManifest]:
        return sorted(self._by_name.values(), key=lambda item: item.name)

    def get(self, name: str) -> SkillManifest | None:
        return self._by_name.get(name)

    def capability_for(self, skill: str, operation: str) -> str:
        manifest = self.get(skill)
        if manifest is None:
            raise KeyError(f"Unknown skill: {skill}")

        capability = manifest.operation_capabilities.get(operation)
        if capability is None:
            raise KeyError(f"Missing capability mapping for {skill}.{operation}")

        return capability

    def all_capabilities(self) -> set[str]:
        capabilities: set[str] = set()
        for manifest in self._by_name.values():
            capabilities.update(manifest.operation_capabilities.values())
        return capabilities


def default_registry() -> SkillRegistry:
    return SkillRegistry(
        [
            SkillManifest(
                name="system",
                version="0.1.0",
                requirements=[],
                operation_capabilities={
                    "catalog": "system.catalog.read",
                    "ping": "system.ping.read",
                    "echo": "system.echo.read",
                },
            ),
            SkillManifest(
                name="notes",
                version="0.1.0",
                requirements=["Local note store"],
                operation_capabilities={
                    "create": "notes.write",
                },
            ),
            SkillManifest(
                name="reminders",
                version="0.1.0",
                requirements=["Reminder read permissions", "Reminder write permissions"],
                operation_capabilities={
                    "list": "reminders.read",
                    "create": "reminders.write",
                },
            ),
            SkillManifest(
                name="imessage",
                version="0.1.0",
                requirements=["Messages Full Disk Access", "Automation access for sending"],
                operation_capabilities={
                    "list_chats": "imessage.read",
                    "send": "imessage.send",
                },
            ),
        ]
    )
