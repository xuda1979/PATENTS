"""Deterministic software examples for the disclosed deployment protocol.

No patient data, stimulation hardware, LLM calls, model training or clinical
evaluation. All resource quantities are dimensionless. This is a sequential
specification; it does not implement interrupt exclusion, persistence or crypto.
"""
from dataclasses import dataclass, replace
from hashlib import sha256
import json
from pathlib import Path


def digest(weights):
    return sha256(json.dumps(weights, separators=(",", ":")).encode()).hexdigest()


@dataclass(frozen=True)
class Package:
    sequence: int = 1
    weights: tuple = (2, -1, 0, 3)
    weight_hash: str = digest((2, -1, 0, 3))
    input_hash: str = "input-v1"
    contract_hash: str = "contract-v1"
    expiry_sample: int = 100
    authenticated: bool = True  # Models a completed, external authentication check.


@dataclass(frozen=True)
class Ticket:
    number: int
    package: Package
    epoch: int
    sample: int
    budget: int
    predecessor: int


class Supervisor:
    def __init__(self, spent=8):
        self.limit, self.spent, self.reserved = 10, spent, 0
        self.contract_hash, self.input_hash = "contract-v1", "input-v1"
        self.epoch, self.sample, self.sequence = 0, 0, 0
        self.active = None
        self.busy = False
        self.history_known = True
        self.ticket_counter = 0
        self.tickets = {}
        self.started = set()
        self.events = []

    def log(self, event, **fields):
        self.events.append(dict(event=event, sequence=self.sequence, epoch=self.epoch,
                                spent=self.spent, reserved=self.reserved, **fields))
        assert 0 <= self.spent and 0 <= self.reserved
        assert self.spent + self.reserved <= self.limit

    def validate(self, p):
        if not self.history_known:
            return "UNKNOWN_HISTORY"
        if not p.authenticated:
            return "UNAUTHENTICATED"
        if p.weight_hash != digest(p.weights):
            return "ACTUAL_BYTES_CHANGED"
        if p.input_hash != self.input_hash or p.contract_hash != self.contract_hash:
            return "CONFIG_MISMATCH"
        if p.expiry_sample < self.sample:
            return "EXPIRED_PACKAGE"
        if p.sequence <= self.sequence:
            return "REPLAY_SEQUENCE"
        return "VALID"

    def prepare(self, p, budget=1, phase_compatible=True):
        code = self.validate(p)
        if code == "VALID":
            if self.busy:
                code = "PACKET_UNFINISHED"
            elif not phase_compatible:
                code = "STATE_INCOMPATIBLE"
            elif budget < 0 or self.spent + self.reserved + budget > self.limit:
                code = "BUDGET_REJECTED"
        if code != "VALID":
            self.log(code)
            return code
        self.reserved += budget
        self.epoch += 1
        self.ticket_counter += 1
        t = Ticket(self.ticket_counter, p, self.epoch, self.sample, budget, self.sequence)
        self.tickets[t.number] = t
        self.log("PREPARED", ticket=t.number)
        return t

    def cancel(self, t, reason="CANCELLED"):
        if t.number in self.tickets and t.number not in self.started:
            del self.tickets[t.number]
            self.reserved -= t.budget
            self.epoch += 1
        self.log(reason)
        return reason

    def fresh(self, t):
        return (self.tickets.get(t.number) == t and t.number not in self.started
                and t.epoch == self.epoch and t.sample == self.sample
                and not self.busy and self.history_known
                and t.package.contract_hash == self.contract_hash
                and t.package.input_hash == self.input_hash
                and t.package.expiry_sample >= self.sample)

    def commit(self, t):
        # In firmware these checks, active publication and reservation ownership
        # must share one bounded exclusion domain with supervisor state writers.
        if not self.fresh(t) or self.sequence != t.predecessor:
            return self.cancel(t, "STALE_HANDOVER")
        self.active = (t.package.weight_hash, t.package.input_hash, t.package.contract_hash)
        self.sequence = t.package.sequence
        self.log("ACTIVATED")
        return "ACTIVATED"

    def start(self, t):
        if t.number in self.started:
            self.log("PERMIT_ALREADY_USED")
            return "PERMIT_ALREADY_USED"
        if not self.fresh(t) or self.sequence != t.package.sequence:
            return self.cancel(t, "STALE_OUTPUT_PERMIT")
        self.started.add(t.number)
        self.busy = True
        self.epoch += 1
        self.log("PACKET_STARTED")
        return "PACKET_STARTED"

    def finish(self, t):
        assert self.busy and t.number in self.started
        # Assumes the readback confirms that the complete reserved packet ran.
        # Hardware fault compensation is a separate implementation requirement.
        self.spent += t.budget
        self.reserved -= t.budget
        del self.tickets[t.number]
        self.busy = False
        self.epoch += 1
        self.log("PACKET_COMPLETED")


def run():
    cases = []

    def save(name, supervisor, observed, expected):
        assert observed == expected, (name, observed, expected)
        cases.append(dict(case=name, observed=observed, expected=expected,
                          passed=True, trace=supervisor.events))

    s = Supervisor(); t = s.prepare(Package()); s.commit(t); s.start(t); s.finish(t)
    save("valid_update_preserves_spent", s, (s.spent, s.reserved, s.sequence), (9, 0, 1))

    s = Supervisor(); p = Package(); assert s.validate(p) == "VALID"
    s.contract_hash = "contract-v2"; s.epoch += 1
    save("contract_changed_after_receive", s, s.prepare(p), "CONFIG_MISMATCH")

    s = Supervisor(); t = s.prepare(Package()); s.spent += 1; s.epoch += 1
    save("budget_changed_after_prepare", s, s.commit(t), "STALE_HANDOVER")

    s = Supervisor(); t = s.prepare(Package()); s.contract_hash = "contract-v2"; s.epoch += 1
    save("contract_changed_after_prepare", s, s.commit(t), "STALE_HANDOVER")

    s = Supervisor(); s.busy = True
    save("mid_packet_update", s, s.prepare(Package()), "PACKET_UNFINISHED")

    s = Supervisor()
    save("input_version_mismatch", s, s.prepare(replace(Package(), input_hash="input-v2")), "CONFIG_MISMATCH")

    s = Supervisor()
    save("deployed_quantized_bytes_changed", s, s.prepare(replace(Package(), weights=(3, -1, 0, 3))), "ACTUAL_BYTES_CHANGED")

    s = Supervisor(); s.sample = 101
    save("expired_package", s, s.prepare(Package()), "EXPIRED_PACKAGE")

    s = Supervisor(); s.sequence = 1
    save("replayed_deployment_sequence", s, s.prepare(Package()), "REPLAY_SEQUENCE")

    s = Supervisor()
    save("phase_state_incompatible", s, s.prepare(Package(), phase_compatible=False), "STATE_INCOMPATIBLE")

    s = Supervisor()
    save("spent_8_plus_first_packet_3", s, s.prepare(Package(), budget=3), "BUDGET_REJECTED")

    s = Supervisor(); t = s.prepare(Package(), budget=2); s.commit(t); s.start(t); s.finish(t)
    # A rollback can load old content only under a new sequence; a silent first
    # packet costs zero, and must not restore the physical budget.
    old_content = (1, -1, 0, 2)
    t = s.prepare(replace(Package(), sequence=2, weights=old_content, weight_hash=digest(old_content)), budget=0)
    s.commit(t); s.start(t); s.finish(t)
    outcome = s.prepare(replace(Package(), sequence=3), budget=1)
    save("rollback_does_not_refill_budget", s, (s.spent, outcome), (10, "BUDGET_REJECTED"))

    s = Supervisor(); t = s.prepare(Package()); s.commit(t); s.start(t)
    save("one_shot_output_permit", s, s.start(t), "PERMIT_ALREADY_USED")

    s = Supervisor(); t = s.prepare(Package()); s.commit(t); s.epoch += 1
    save("state_changed_before_first_packet", s, s.start(t), "STALE_OUTPUT_PERMIT")

    s = Supervisor(); s.history_known = False
    save("unknown_history_after_restart", s, s.prepare(Package()), "UNKNOWN_HISTORY")

    result = dict(kind="deterministic_sequential_software_examples", dimensionless=True,
                  case_count=len(cases), passed=sum(c["passed"] for c in cases),
                  limitations=["No real hardware or patient data", "No clinical or timing claim",
                               "Sequential specification, not concurrency verification",
                               "Crypto and persistence are implementation requirements, not exercised"],
                  cases=cases)
    (Path(__file__).parent / "scenario_results.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: result[k] for k in ["kind", "case_count", "passed"]}))


if __name__ == "__main__":
    run()
