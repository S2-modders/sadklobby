"""
Match wagers: gold the players of a match bet on winning it (maintainer rules 2026-10-12).

What the client gives us [known, static; docs/message-catalog.md, 0xDB6 RegisterGame]:
  * The host sets the wager in the pre-game room, from 0 to its own gold. A change clears every human
    slot's ready state; "ready" needs wager <= the player's own gold and, with a wager, no AI slot.
  * Every client sends RegisterGame (0xDB6) with the same GameID, Wager and six AvatarIDs (the slots'
    avatar ids = perm ids, 0 for an empty slot).
  * FinishGame (0xDC0) names ONE winning avatar, the same on every client; allies that also won are
    not listed. The client moves no gold and shows no wager result.
  * The referee's result codes (ERefereeResult, table S 0087aee0) include MismatchingPlayerlist 8,
    MismatchedWager 9 and NotEnoughCredits 15.

Server rules:
  * Registration. With a wager, a registration is refused with 9 when its wager differs from the
    match's, with 8 when its player list differs, and with 15 when the player's gold is below the
    wager. A match without a wager is never refused (nothing to check).
  * Settlement. No gold moves until the match is over: when every registered player has reported
    (FinishGame, GiveUpGame, or its referee connection closed) and all FinishGame reports name the
    same registered player, each other player pays it the wager. So a match the server does not see
    the end of, or whose reports disagree, costs nobody anything.
  * Teams. The server does not know the teams, and the one named winner's allies cannot be told from
    its opponents. So only a match of exactly two players is settled; in a larger one no gold moves
    and the players are told. [TODO: teams from the gamebridge mod]
"""
import threading

from . import economy
from .log import log
from .village import BitReader

RESULT_OK = 0
RESULT_MISMATCHING_PLAYERLIST = 8
RESULT_MISMATCHED_WAGER = 9
RESULT_NOT_ENOUGH_CREDITS = 15

_lock = threading.Lock()
_matches = {}                                 # game_id -> _Match
#: Set by dispatch: (perm_id, text) -> a server line in the player's chat (kept until it is back).
NOTIFY = None


class _Match:
    def __init__(self, wager, players):
        self.wager = wager
        self.players = frozenset(players)     # the avatar ids of the registration (non-zero slots)
        self.registered = set()
        self.reports = {}                     # perm_id -> named winner, or None (gave up / gone)


def reset_for_tests():
    with _lock:
        _matches.clear()


def parse_register_game(inner):
    """RegisterGame's fields (MSB-first bit stream): GameID 32, MapGUID 128, MapName u8 len + bytes,
    MapSettings u8 len + bytes, RankedGame 1 bit, Wager 32, AIPlayer 8 (a count), AvatarID 6 x 32.
    Returns (wager, ai_count, avatar_ids) or None when the body is shorter than that."""
    r = BitReader(inner)
    try:
        r.read(32)
        r.read(128)
        r.read(8 * r.read(8))
        r.read(8 * r.read(8))
        r.read(1)
        wager = r.read(32)
        ai_count = r.read(8)
        avatars = tuple(r.read(32) for _ in range(6))
    except ValueError:
        return None
    return wager, ai_count, avatars


def register(game_id, perm_id, wager, avatars):
    """One player's RegisterGame. Returns the ERefereeResult code to answer with (0 = accepted)."""
    players = frozenset(a for a in avatars if a)
    with _lock:
        m = _matches.get(game_id)
        if m is None or perm_id in m.registered:          # a new match, or a rematch on this GameID
            m = _matches[game_id] = _Match(wager, players)
        if wager or m.wager:
            if wager != m.wager:
                return RESULT_MISMATCHED_WAGER
            if players != m.players:
                return RESULT_MISMATCHING_PLAYERLIST
            if economy.load(perm_id).gold < wager:
                return RESULT_NOT_ENOUGH_CREDITS
        m.registered.add(perm_id)
    return RESULT_OK


def report(game_id, perm_id, winner):
    """One player's end of the match: `winner` is the avatar its FinishGame named, None for a give-up
    or a closed connection. A player's first FinishGame counts. Settles when every registered player
    has reported."""
    with _lock:
        m = _matches.get(game_id)
        if m is None or perm_id not in m.registered:
            return
        if m.reports.get(perm_id) is None:
            m.reports[perm_id] = winner
        if set(m.reports) < m.registered:
            return
        del _matches[game_id]
    _settle(game_id, m)


def connection_closed(perm_id):
    """A referee connection closed: a registered player that has not reported is gone."""
    with _lock:
        open_games = [g for g, m in _matches.items() if perm_id in m.registered and perm_id not in m.reports]
    for game_id in open_games:
        log(f"  [WAGER] match {game_id}: {perm_id} left without a report")
        report(game_id, perm_id, None)


def _tell(perm_ids, text):
    if NOTIFY is not None:
        for perm_id in perm_ids:
            NOTIFY(perm_id, text)


def _settle(game_id, m):
    if not m.wager:
        return
    named = {w for w in m.reports.values() if w is not None}
    if len(m.players) != 2:
        why = "the server cannot tell teams apart in a match of more than two players"
    elif m.registered != m.players:
        why = "not every player registered with the server"
    elif len(named) != 1:
        why = "the players' results disagree" if named else "nobody reported a winner"
    elif next(iter(named)) not in m.registered:
        why = "the reported winner is not a player of the match"
    else:
        why = None
    if why is not None:
        log(f"  [WAGER] match {game_id}: wager {m.wager} NOT settled — {why} (reports {m.reports})")
        _tell(m.registered, f"Wager of {m.wager} gold: no gold was moved - {why}.")
        return
    winner = next(iter(named))
    won = 0
    for loser in sorted(m.registered - {winner}):
        w = economy.load(loser)
        paid = min(m.wager, w.gold)
        w.gold -= paid
        economy.persist(loser)
        won += paid
        log(f"  [WAGER] match {game_id}: {loser} pays {paid} gold (now {w.gold})")
        _tell((loser,), f"Wager: you lost {paid} gold.")
    w = economy.load(winner)
    w.gold += won
    economy.persist(winner)
    log(f"  [WAGER] match {game_id}: {winner} wins {won} gold (now {w.gold})")
    _tell((winner,), f"Wager: you won {won} gold.")
