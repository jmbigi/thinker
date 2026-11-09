from dsl import (Subject, Resource, Action, AccessRule, AccessPolicy,
                 rule, has_role)

class TestSubject:
    def test_user_match(self):
        subj = Subject("alice")
        assert subj.matches({"username": "alice"}) is True
        assert subj.matches({"username": "bob"}) is False

    def test_role_match(self):
        subj = Subject("admin", "role")
        assert subj.matches({"roles": ["admin", "user"]}) is True
        assert subj.matches({"roles": ["user"]}) is False

class TestResource:
    def test_match(self):
        res = Resource("doc1", "document")
        assert res.matches({"resource": "doc1", "resource_type": "document"}) is True
        assert res.matches({"resource": "doc2", "resource_type": "document"}) is False
        assert res.matches({"resource": "doc1", "resource_type": "file"}) is False

class TestAction:
    def test_match(self):
        act = Action("read")
        assert act.matches({"action": "read"}) is True
        assert act.matches({"action": "write"}) is False

class TestAccessRule:
    def test_all_match(self):
        rule = AccessRule(Subject("alice"), Resource("doc1", "document"), Action("read"))
        ctx = {"username": "alice", "resource": "doc1", "resource_type": "document", "action": "read"}
        assert rule.evaluate(ctx) is True

    def test_subject_mismatch(self):
        rule = AccessRule(Subject("alice"), Resource("doc1", "document"), Action("read"))
        ctx = {"username": "bob", "resource": "doc1", "resource_type": "document", "action": "read"}
        assert rule.evaluate(ctx) is False

    def test_condition(self):
        rule = AccessRule(condition=lambda ctx: ctx.get("time", 0) < 12)
        assert rule.evaluate({"time": 10}) is True
        assert rule.evaluate({"time": 14}) is False

    def test_none_fields_skip_check(self):
        rule = AccessRule(subject=Subject("alice"))
        assert rule.evaluate({"username": "alice"}) is True
        assert rule.evaluate({"username": "bob"}) is False

class TestAccessPolicy:
    def test_any_rule_matches(self):
        policy = AccessPolicy()
        policy.add_rule(AccessRule(Subject("alice")))
        policy.add_rule(AccessRule(Subject("bob")))
        assert policy.check({"username": "alice"}) is True
        assert policy.check({"username": "charlie"}) is False

    def test_from_rules(self):
        rules = [AccessRule(Subject("alice")), AccessRule(Subject("bob"))]
        policy = AccessPolicy.from_rules(rules)
        assert policy.check({"username": "bob"}) is True

class TestRuleFactory:
    def test_creates_rule(self):
        r = rule("alice", "read", "doc1")
        assert isinstance(r, AccessRule)
        assert r.subject.name == "alice"
        assert r.action.name == "read"
        assert r.resource.name == "doc1"

    def test_optional_fields(self):
        r = rule(None, "read", None)
        assert r.subject is None
        assert r.resource is None
        assert r.action.name == "read"

class TestHasRole:
    def test_matches_any_role(self):
        checker = has_role("admin", "editor")
        assert checker({"roles": ["viewer", "editor"]}) is True
        assert checker({"roles": ["viewer"]}) is False
        assert checker({}) is False
