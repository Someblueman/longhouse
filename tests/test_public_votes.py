"""Public decisions retain attribution without leaking future or private state."""
import copy
import json

from house.body import export, voting_view
from tests.support import HouseCase
from tests import test_council, test_shelf


class PublicVotingTests(HouseCase):
    def test_historical_replay_legacy_author_and_successful_inbox_receipts(self):
        before = export(self.record)["frames"]
        state = self.record.read()[0]
        self.record.append("propose", "alice", {"proposal": "old-rule", "text": "Exact old wording",
            "reason": "An earlier proposal", "base": state["rule_revision"]})
        proposal_frame = export(self.record)["frames"][-1]
        proposal = proposal_frame["voting"]["proposals"][0]
        self.assertEqual("Alice", proposal["author"]["name"])
        self.assertEqual("legacy", proposal["mode"])
        self.assertFalse(proposal["stale"])
        self.record.append("arrive", "watch-keeper", {"name": "Clock"})
        stamp = self.record.read()[0]["at"]
        self.record.append("say", "watch-keeper", {"text": "house-inbox-v1 " + json.dumps({
            "checked_through": stamp, "accepted": ["PRIVATE-METADATA"]})})
        for actor, payload in [("alice", {"checked_through": stamp + 999}),
                               ("watch-keeper", []), ("watch-keeper", {"checked_through": 1e100})]:
            self.record.append("say", actor, {"text": "house-inbox-v1 " + json.dumps(payload)})
        frames = export(self.record)["frames"]
        self.assertEqual(before, frames[:len(before)])
        self.assertEqual(proposal_frame, frames[len(before)])
        self.assertIsNone(proposal_frame["voting"]["inbox_checked_at"])
        self.assertEqual(stamp, frames[-1]["voting"]["inbox_checked_at"])
        self.assertNotIn("PRIVATE-METADATA", json.dumps(frames))

    def test_real_ballots_author_exclusion_and_rejection_are_preserved(self):
        h = test_shelf.ShelfTests(); h.setUp(); h.publish()
        h.send("choice-open", actor="other", choice="round", milestones={
            k: {"milestone": "Demo"} for k in "abc"})
        h.send("choice-vote", choice="round", idea="a", reason="Own idea")
        h.send("choice-vote", actor="v1", choice="round", idea="b", reason="Prefer the second")
        h.state["proposals"] = {}
        h.state["shelf_trials"] = {"secret": "TRIAL-ONLY"}
        times = {seq: seq * 10 for seq in range(1, 40)}
        before = voting_view(h.state, {"v1": {"agent": "agy"}}, times)
        first = before["choices"][0]
        self.assertEqual("open", first["status"])
        self.assertEqual([False, True], [v["counted"] for v in first["votes"]])
        self.assertEqual("agy", first["votes"][1]["resident"]["agent"])
        self.assertEqual(3, len(first["candidates"]))
        h.send("choice-vote", actor="v2", choice="round", idea="b", reason="Also second")
        h.send("choice-vote", actor="v3", choice="round", idea="c", reason="Prefer third")
        closed = voting_view(h.state, {}, times)["choices"][0]
        self.assertEqual("closed", closed["status"])
        self.assertEqual("b", closed["winner"])
        self.assertEqual(2, len(first["votes"]))
        self.assertNotIn("TRIAL-ONLY", json.dumps(before))
        # The revised reducer records a rejected shortlist with explicit null votes.
        h = test_shelf.ShelfTests(); h.setUp(); h.publish()
        h.send("choice-open", actor="other", choice="reject", milestones={
            k: {"milestone": "Demo"} for k in "abc"})
        h.state["shelf"]["choices"]["reject"]["selection_version"] = 2
        for actor in ("v1", "v2", "v3"):
            h.send("choice-vote", actor=actor, choice="reject", idea=None, reason="None worth a slot")
        h.state["proposals"] = {}
        rejected = voting_view(h.state, {}, times)["choices"][0]
        self.assertEqual("rejected", rejected["status"])
        self.assertIsNone(rejected["winner"])
        self.assertTrue(all(v["idea"] is None and v["counted"] for v in rejected["votes"]))

    def test_council_trial_endorsements_notice_and_staleness(self):
        h = test_council.CouncilTests(); h.setUp(); h.authorize(); h.ready()
        before = copy.deepcopy(h.state)
        public = voting_view(h.state, {"bob": {"agent": "muse"}}, {})
        p = public["proposals"][0]
        self.assertEqual(["bob", "carol"], [v["resident"]["id"] for v in p["endorsements"]])
        self.assertEqual("muse", p["endorsements"][0]["resident"]["agent"])
        self.assertEqual(86400, p["notice"]["until"] - p["notice"]["at"])
        self.assertTrue(p["notice"]["url"].startswith("https://github.com/Someblueman/emberhall/issues/1#issuecomment-"))
        self.assertEqual(before, h.state)
        self.assertNotIn("base64", json.dumps(public))
        h.state["rule_revision"] = "changed"
        self.assertTrue(voting_view(h.state, {}, {})["proposals"][0]["stale"])
        h.state["proposals"]["rule-one"].update(status="enacted", ratification={"method":"direct-owner"})
        h.state["council"]["rules"]["rule-one"] = {"status": "repealed"}
        p = voting_view(h.state, {}, {})["proposals"][0]
        self.assertFalse(p["stale"])
        self.assertEqual("repealed", p["rule_status"])
        self.assertEqual("direct-owner", p["ratification"])
