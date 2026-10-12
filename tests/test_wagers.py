"""
Match wagers (offline, maintainer rules 2026-10-12, sadk_lobby/wagers.py): a registration with a wager
is checked against the match's (ERefereeResult 8 / 9 / 15); gold moves only when the match is over and
every report names the same winner; only two-player matches are settled.

Run:  python tests/test_wagers.py
"""
import os
import struct
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)
os.environ["SADK_STORE_PATH"] = os.path.join(tempfile.mkdtemp(), "players.json")

from sadk_lobby import config, economy, players, referee, rewards, savegame, store, wagers  # noqa: E402
from sadk_lobby.village import BitWriter  # noqa: E402

GAME = 77


def _char(name, gold):
    store.get_or_create_account(name)
    blob = savegame.build(savegame.Save(gold=gold, glod=100))
    return int(store.create_character(name, name, blob)["char_id"])


def _fresh():
    store.reset_for_tests(os.environ["SADK_STORE_PATH"])
    economy.reset_for_tests()
    rewards.reset_for_tests()
    wagers.reset_for_tests()
    notices = []
    wagers.NOTIFY = lambda perm, text: notices.append((perm, text))
    return notices


def _gold(perm):
    economy.reset_for_tests()                                     # a server restart: from the save
    return economy.load(perm).gold


def register_body(game_id, wager, avatars, ranked=0, ai=0, map_name=b"Kleeblatt", settings=b"012"):
    """RegisterGame as the client writes it (S 00479840): the 1-bit RankedGame shifts what follows."""
    w = BitWriter().write(game_id, 32)
    for b in bytes(range(16)):                                    # MapGUID, raw
        w.write(b, 8)
    for text in (map_name, settings):
        w.write(len(text), 8)
        for b in text:
            w.write(b, 8)
    w.write(ranked, 1).write(wager, 32).write(ai, 8)
    for a in tuple(avatars) + (0,) * (6 - len(avatars)):
        w.write(a, 32)
    return w.bytes()


def test_parse():
    body = register_body(GAME, 250, (100002, 100006), ranked=1, ai=0)
    assert wagers.parse_register_game(body) == (250, 0, (100002, 100006, 0, 0, 0, 0))
    assert wagers.parse_register_game(struct.pack(">I", GAME)) is None      # GameID only
    print("RegisterGame bit stream: wager, AI count, six avatar ids OK")


def test_two_players_winner_takes_the_wager():
    notices = _fresh()
    a, b = _char("Anna", 1000), _char("Bert", 400)
    both = (a, b)
    assert wagers.register(GAME, a, 300, both) == 0 and wagers.register(GAME, b, 300, both) == 0
    wagers.report(GAME, a, a)                                     # the winner's FinishGame
    assert _gold(a) == 1000                                       # nothing moves on one report
    wagers.report(GAME, b, a)                                     # the loser's names the same avatar
    assert (_gold(a), _gold(b)) == (1300, 100)
    assert notices == [(b, "Wager: you lost 300 gold."), (a, "Wager: you won 300 gold.")]
    wagers.report(GAME, b, a)                                     # a repeat finds no open match
    assert (_gold(a), _gold(b)) == (1300, 100)
    print("two players: the loser pays the winner once, after both reported OK")


def test_loser_leaves_without_a_report():
    _fresh()
    a, b = _char("Anna", 1000), _char("Bert", 400)
    wagers.register(GAME, a, 300, (a, b))
    wagers.register(GAME, b, 300, (a, b))
    wagers.connection_closed(b)                                   # quits: its referee connection closes
    assert _gold(b) == 400
    wagers.report(GAME, a, a)
    assert (_gold(a), _gold(b)) == (1300, 100)
    print("a player that leaves has reported nothing; the remaining winner is paid OK")


def test_no_gold_moves():
    notices = _fresh()
    a, b, c = _char("Anna", 1000), _char("Bert", 400), _char("Cleo", 900)
    # the reports disagree
    wagers.register(GAME, a, 300, (a, b))
    wagers.register(GAME, b, 300, (a, b))
    wagers.report(GAME, a, a)
    wagers.report(GAME, b, b)
    # nobody reports a winner
    wagers.register(GAME + 1, a, 300, (a, b))
    wagers.register(GAME + 1, b, 300, (a, b))
    wagers.report(GAME + 1, a, None)
    wagers.connection_closed(b)
    # three players: allies of the winner cannot be told from its opponents
    for p in (a, b, c):
        assert wagers.register(GAME + 2, p, 300, (a, b, c)) == 0
    for p in (a, b, c):
        wagers.report(GAME + 2, p, a)
    # one of two never registered
    wagers.register(GAME + 3, a, 300, (a, b))
    wagers.report(GAME + 3, a, a)
    assert (_gold(a), _gold(b), _gold(c)) == (1000, 400, 900)
    assert len(notices) == 2 + 2 + 3 + 1 and all("no gold was moved" in t for _p, t in notices)
    # a match without a wager is silent
    wagers.register(GAME + 4, a, 0, (a, b))
    wagers.register(GAME + 4, b, 0, (a, b))
    wagers.report(GAME + 4, a, a)
    wagers.report(GAME + 4, b, a)
    assert len(notices) == 8 and (_gold(a), _gold(b)) == (1000, 400)
    print("disagreeing reports, no winner, three players, a missing player, no wager: no gold moves OK")


def test_refusals():
    _fresh()
    a, b = _char("Anna", 1000), _char("Bert", 400)
    assert wagers.register(GAME, a, 500, (a, b)) == 0
    assert wagers.register(GAME, b, 500, (a, b)) == wagers.RESULT_NOT_ENOUGH_CREDITS == 15
    assert wagers.register(GAME, b, 300, (a, b)) == wagers.RESULT_MISMATCHED_WAGER == 9
    assert wagers.register(GAME, b, 500, (b,)) == wagers.RESULT_MISMATCHING_PLAYERLIST == 8
    # without a wager nothing is checked: a registration must never fail on it
    assert wagers.register(GAME + 1, a, 0, (a, b)) == 0 and wagers.register(GAME + 1, b, 0, ()) == 0
    # a rematch on the same GameID starts a new match
    assert wagers.register(GAME, a, 100, (a, b)) == 0 and wagers.register(GAME, b, 100, (a, b)) == 0
    print("refusals 15 / 9 / 8 only with a wager; rematch on the same GameID OK")


class FakeConn:
    is_referee = True

    def __init__(self, perm):
        self.id = perm
        self.alive = True
        self.player = players.resolve_by_perm(perm)
        self.raw = []

    def send_raw(self, data):
        self.raw.append(data)

    def last(self):
        payload = self.raw[-1][config.PREFIX_SIZE:]
        blen = struct.unpack_from("<I", payload, 10)[0]
        return struct.unpack_from("<I", payload, 6)[0] & 0xFFF, payload[14:14 + blen]


def test_through_the_referee():
    _fresh()
    a, b = _char("Anna", 1000), _char("Bert", 400)
    ca, cb = FakeConn(a), FakeConn(b)
    send = lambda conn, msg, body: referee.handle_frame(conn, referee.referee_payload(msg, body))
    # Bert cannot cover 500: Ack, then Result 15 with an empty FailReason and no GameSeed
    send(ca, config.REF_REGISTER_GAME, register_body(GAME, 500, (a, b)))
    send(cb, config.REF_REGISTER_GAME, register_body(GAME, 500, (a, b)))
    assert ca.last() == (config.REF_REGISTER_RESULT, struct.pack(">III", GAME, 0, config.REF_GAME_SEED))
    assert cb.last() == (config.REF_REGISTER_RESULT, struct.pack(">II", GAME, 15) + b"\x00")
    # the match is set up again with 200 and played; both FinishGames name Anna
    send(ca, config.REF_REGISTER_GAME, register_body(GAME, 200, (a, b)))
    send(cb, config.REF_REGISTER_GAME, register_body(GAME, 200, (a, b)))
    assert cb.last()[1] == struct.pack(">III", GAME, 0, config.REF_GAME_SEED)
    finish = struct.pack(">I", GAME) + bytes(range(16)) + bytes([3]) + b"012" + struct.pack(">I", a)
    send(ca, config.REF_FINISH_GAME, finish)
    send(cb, config.REF_FINISH_GAME, finish)
    assert cb.last()[0] == config.REF_FINISH_RESULT
    assert (_gold(a), _gold(b)) == (1200, 200)                    # the match took 0 minutes: no reward
    print("RegisterGame refusal on the wire, and a wagered match through the referee handler OK")


if __name__ == "__main__":
    test_parse()
    test_two_players_winner_takes_the_wager()
    test_loser_leaves_without_a_report()
    test_no_gold_moves()
    test_refusals()
    test_through_the_referee()
    print("\nAll wager tests PASSED")
