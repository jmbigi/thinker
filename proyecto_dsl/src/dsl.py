from typing import Any, Callable, Dict, List, Optional


class Subject:
    def __init__(self, name: str, subject_type: str = "user"):
        self.name = name
        self.subject_type = subject_type

    def matches(self, context: Dict[str, Any]) -> bool:
        if self.subject_type.lower() == "role":
            return context.get("roles", []).count(self.name) > 0
        return context.get("username", "") == self.name


class Resource:
    def __init__(self, name: str, resource_type: str = "entity"):
        self.name = name
        self.resource_type = resource_type

    def matches(self, context: Dict[str, Any]) -> bool:
        res_ref = context.get("resource", "")
        res_type = context.get("resource_type", "")
        return res_ref == self.name and res_type == self.resource_type


class Action:
    def __init__(self, name: str):
        self.name = name

    def matches(self, context: Dict[str, Any]) -> bool:
        return context.get("action", "") == self.name


class AccessRule:
    def __init__(self,
                 subject: Optional[Subject] = None,
                 resource: Optional[Resource] = None,
                 action: Optional[Action] = None,
                 condition: Optional[Callable[[Dict[str, Any]], bool]] = None):
        self.subject = subject
        self.resource = resource
        self.action = action
        self.condition = condition

    def evaluate(self, context: Dict[str, Any]) -> bool:
        if self.subject and not self.subject.matches(context):
            return False
        if self.resource and not self.resource.matches(context):
            return False
        if self.action and not self.action.matches(context):
            return False
        if self.condition and not self.condition(context):
            return False
        return True


class AccessPolicy:
    def __init__(self):
        self.rules: List[AccessRule] = []

    def add_rule(self, rule: AccessRule) -> 'AccessPolicy':
        self.rules.append(rule)
        return self

    def check(self, context: Dict[str, Any]) -> bool:
        return any(rule.evaluate(context) for rule in self.rules)

    @classmethod
    def from_rules(cls, rules: List[AccessRule]) -> 'AccessPolicy':
        policy = cls()
        for rule in rules:
            policy.add_rule(rule)
        return policy


def rule(subject: Optional[str],
         action: Optional[str],
         resource: Optional[str],
         condition: Optional[Callable[[Dict[str, Any]], bool]] = None) -> AccessRule:
    return AccessRule(
        subject=Subject(subject) if subject else None,
        action=Action(action) if action else None,
        resource=Resource(resource) if resource else None,
        condition=condition
    )


def has_role(*roles: str) -> Callable[[Dict[str, Any]], bool]:
    def _checker(ctx: Dict[str, Any]) -> bool:
        ctx_roles = ctx.get("roles", [])
        return any(role in roles for role in ctx_roles)
    return _checker
