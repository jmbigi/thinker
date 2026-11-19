from collections.abc import Callable
from typing import Any


class Subject:
    def __init__(self, name: str, subject_type: str = "user"):
        self.name = name
        self.subject_type = subject_type

    def matches(self, context: dict[str, Any]) -> bool:
        if self.subject_type.lower() == "role":
            return context.get("roles", []).count(self.name) > 0
        return context.get("username", "") == self.name


class Resource:
    def __init__(self, name: str, resource_type: str = "entity"):
        self.name = name
        self.resource_type = resource_type

    def matches(self, context: dict[str, Any]) -> bool:
        res_ref = context.get("resource", "")
        res_type = context.get("resource_type", "")
        return res_ref == self.name and res_type == self.resource_type


class Action:
    def __init__(self, name: str):
        self.name = name

    def matches(self, context: dict[str, Any]) -> bool:
        return context.get("action", "") == self.name


class AccessRule:
    def __init__(self,
                 subject: Subject | None = None,
                 resource: Resource | None = None,
                 action: Action | None = None,
                 condition: Callable[[dict[str, Any]], bool] | None = None):
        self.subject = subject
        self.resource = resource
        self.action = action
        self.condition = condition

    def evaluate(self, context: dict[str, Any]) -> bool:
        if self.subject and not self.subject.matches(context):
            return False
        if self.resource and not self.resource.matches(context):
            return False
        if self.action and not self.action.matches(context):
            return False
        return not (self.condition and not self.condition(context))


class AccessPolicy:
    def __init__(self):
        self.rules: list[AccessRule] = []

    def add_rule(self, rule: AccessRule) -> 'AccessPolicy':
        self.rules.append(rule)
        return self

    def check(self, context: dict[str, Any]) -> bool:
        return any(rule.evaluate(context) for rule in self.rules)

    @classmethod
    def from_rules(cls, rules: list[AccessRule]) -> 'AccessPolicy':
        policy = cls()
        for rule in rules:
            policy.add_rule(rule)
        return policy


def rule(subject: str | None,
         action: str | None,
         resource: str | None,
         condition: Callable[[dict[str, Any]], bool] | None = None) -> AccessRule:
    return AccessRule(
        subject=Subject(subject) if subject else None,
        action=Action(action) if action else None,
        resource=Resource(resource) if resource else None,
        condition=condition
    )


def has_role(*roles: str) -> Callable[[dict[str, Any]], bool]:
    def _checker(ctx: dict[str, Any]) -> bool:
        ctx_roles = ctx.get("roles", [])
        return any(role in roles for role in ctx_roles)
    return _checker
