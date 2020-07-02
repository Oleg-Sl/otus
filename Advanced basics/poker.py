#!/usr/bin/env python
# -*- coding: utf-8 -*-

# -----------------
# Реализуйте функцию best_hand, которая принимает на вход
# покерную "руку" (hand) из 7ми карт и возвращает лучшую
# (относительно значения, возвращаемого hand_rank)
# "руку" из 5ти карт. У каждой карты есть масть(suit) и
# ранг(rank)
# Масти: трефы(clubs, C), пики(spades, S), червы(hearts, H), бубны(diamonds, D)
# Ранги: 2, 3, 4, 5, 6, 7, 8, 9, 10 (ten, T), валет (jack, J), дама (queen, Q), король (king, K), туз (ace, A)
# Например: AS - туз пик (ace of spades), TH - дестяка черв (ten of hearts), 3C - тройка треф (three of clubs)

# Задание со *
# Реализуйте функцию best_wild_hand, которая принимает на вход
# покерную "руку" (hand) из 7ми карт и возвращает лучшую
# (относительно значения, возвращаемого hand_rank)
# "руку" из 5ти карт. Кроме прочего в данном варианте "рука"
# может включать джокера. Джокеры могут заменить карту любой
# масти и ранга того же цвета, в колоде два джокерва.
# Черный джокер '?B' может быть использован в качестве треф
# или пик любого ранга, красный джокер '?R' - в качестве черв и бубен
# любого ранга.

# Одна функция уже реализована, сигнатуры и описания других даны.
# Вам наверняка пригодится itertools.
# Можно свободно определять свои функции и т.п.
# -----------------
from itertools import groupby, takewhile
from operator import itemgetter
from collections import Counter


def get_num_equiv(s):
    """Возвращает числовое представление ранга"""
    try:
        s = int(s)
    except ValueError:
        pass

    if isinstance(s, int):
        return s
    elif s == 'T':
        return 10
    elif s == 'J':
        return 11
    elif s == 'Q':
        return 12
    elif s == 'K':
        return 13
    elif s == 'A':
        return 14


def get_str_equiv(numb):
    """Возвращает строковое представление ранга"""
    if numb <= 9:
        return numb
    elif numb == 10:
        return 'T'
    elif numb == 11:
        return 'J'
    elif numb == 12:
        return 'Q'
    elif numb == 13:
        return 'K'
    elif numb == 14:
        return 'A'


def check_order(cards):
    """Возвращает последовательность из пяти карт идущих подряд"""
    count = 1
    for ind, el in enumerate(cards):
        if ind == 0:
            continue
        if count == 5:
            return cards[ind-count:ind]
        elif cards[ind][0] == cards[ind - 1][0] - 1:
            count += 1
        else:
            count = 1
    if count == 5:
        return cards[ind - count:ind]


def hand_rank(hand):
    """Возвращает значение определяющее ранг 'руки'"""
    ranks = card_ranks(hand)
    if straight_flush(hand):
        return (8, straight_flush(hand))
    elif kind(4, ranks):
        return (7, kind(4, ranks), kind(1, ranks))
    elif kind(3, ranks) and kind(2, ranks):
        return (6, kind(3, ranks), kind(2, ranks))
    elif flush(hand):
        return (5, flush(hand), ranks)
    elif straight(ranks):
        return (4, straight(ranks))
    elif kind(3, ranks):
        return (3, kind(3, ranks), ranks)
    elif two_pair(ranks):
        return (2, two_pair(ranks), ranks)
    elif kind(2, ranks):
        return (1, kind(2, ranks), ranks)
    else:
        return (0, ranks)


def card_ranks(hand):
    """Возвращает список рангов (его числовой эквивалент),
    отсортированный от большего к меньшему"""
    lst_rank = [get_num_equiv(el[0]) for el in hand]
    return sorted(lst_rank)


def straight_flush(hand):
    lst = sorted([(get_num_equiv(el[0]), el[1]) for el in hand], key=itemgetter(1, 0), reverse=True)
    for suit, cards in groupby(lst, lambda k: k[1]):
        cards_order = check_order(list(cards))
        if cards_order:
            return cards_order


def flush(hand):
    """Возвращает масть, если 5 карт одной масти"""
    hand_counter = Counter([card[1] for card in hand])
    for suit, count in hand_counter.items():
        if count >= 5:
            return suit


def straight(ranks):
    """Возвращает True, если отсортированные ранги формируют последовательность 5ти,
    где у 5ти карт ранги идут по порядку (стрит)"""
    rev_ranks = ranks[::-1]
    count = 1
    offset = 0
    for ind, _ in enumerate(rev_ranks[:-1]):
        if count == 5:
            return rev_ranks[ind - 4 - offset]
        elif rev_ranks[ind] == rev_ranks[ind + 1] + 1:
            count += 1
        elif rev_ranks[ind] == rev_ranks[ind + 1]:
            offset += 1
            continue
        else:
            count = 1
            offset = 0
    if count == 5:
        return rev_ranks[ind - 3 - offset]


def kind(n, ranks):
    """Возвращает первый ранг, который n раз встречается в данной руке.
    Возвращает None, если ничего не найдено"""
    for rank, count in Counter(reversed(ranks)).items():
        if count == n:
            return rank
    return None


def two_pair(ranks):
    """Если есть две пары, то возврщает два соответствующих ранга,
    иначе возвращает None"""
    r1 = kind(2, ranks)
    r2 = kind(2, [r for r in ranks if r != r1])
    if r1 and r2:
        return r1, r2


def best_hand(hand):
    """Из "руки" в 7 карт возвращает лучшую "руку" в 5 карт """
    return filtering_card(hand, hand_rank(hand))


def best_wild_hand(hand):
    """best_hand но с джокерами"""
    ranks = list(range(2, 10))
    ranks.extend(['T', 'J', 'Q', 'K', 'A'])
    try:
        ind_b = hand.index('?B')
    except ValueError:
        ind_b = None

    try:
        ind_r = hand.index('?R')
    except ValueError:
        ind_r = None

    if not ind_b and not ind_r:
        return filtering_card(hand, hand_rank(hand))

    comb = None
    hand_comb = None
    for suit_b in ['C', 'S']:
        for suit_r in ['H', 'D']:
            for rank_b in ranks:
                if ind_b is None or f'{rank_b}{suit_b}' in hand:
                    continue
                hand.pop(ind_b)
                hand.insert(ind_b, f'{rank_b}{suit_b}')
                for rank_r in ranks:
                    if not ind_r is None and f'{rank_r}{suit_r}' not in hand:
                        hand.pop(ind_r)
                        hand.insert(ind_r, f'{rank_r}{suit_r}')

                    new_hand = hand_rank(hand)
                    if comb is None:
                        comb = new_hand
                        hand_comb = hand[:]
                        continue
                    comb = compar(comb, new_hand)
                    if comb == new_hand:
                        hand_comb = hand[:]
    return filtering_card(hand_comb, comb)


def compar(hand_1, hand_2):
    """Сравнение двух комбинаций"""
    if hand_1[0] > hand_2[0]:
        return hand_1
    elif hand_1[0] < hand_2[0]:
        return hand_2
    elif hand_1[0] in [2, 3, 4, 8]:
        return hand_1 if hand_1[1] > hand_2[1] else hand_2
    elif hand_1[0] in [6, 7]:
        if hand_1[1] > hand_2[1]:
            return hand_1
        elif hand_1[1] < hand_2[1]:
            return hand_2
        elif hand_1[2] > hand_2[2]:
            return hand_1
        else:
            return hand_2
    elif hand_1[0] == 5:
        return hand_1 if hand_1[2] > hand_2[2] else hand_2
    elif hand_1[0] == 1:
        if hand_1[1] > hand_2[1]:
            return hand_1
        elif hand_1[1] < hand_2[1]:
            return hand_2
        elif max(hand_1[2]) > max(hand_1[2]):
            return hand_1
        else:
            return hand_2
    else:
        return hand_1 if max(hand_1[1]) > max(hand_1[1]) else hand_2


def filtering_card(hand, comb):
    """Возвращает список из 5 карт, в соответствии с переданной комбинацией - comb"""
    print(hand)

    if comb[0] == 8:
        return [f'{get_str_equiv(el[0])}{el[1]}' for el in comb[1]]
    elif comb[0] == 7:
        return [el for el in hand if get_num_equiv(el[0]) in comb[1:]]
    elif comb[0] == 6:
        return [el for el in hand if get_num_equiv(el[0]) in comb[1:]]
    elif comb[0] == 5:
        lst = [el for el in hand if el[1] is comb[1]]
        return sorted(lst)[-5:]
    elif comb[0] == 4:
        ranks = [i for i in range(comb[1] - 4, comb[1] + 1)]
        return [el for el in hand if get_num_equiv(el[0]) in ranks]
    elif comb[0] == 3:
        return 3
    elif comb[0] == 2:
        return [el for el in hand if get_num_equiv(el[0]) in [*comb[1], comb[-1][-1]]]
    elif comb[0] == 1:
        return [el for el in hand if get_num_equiv(el[0]) in [comb[1], *comb[-1]]]
    else:
        return sorted(hand)[:5]


def test_best_hand():
    print("test_best_hand...")
    assert (sorted(best_hand("6C 7C 8C 9C TC 5C JS".split()))
            == ['6C', '7C', '8C', '9C', 'TC'])
    assert (sorted(best_hand("TD TC TH 7C 7D 8C 8S".split()))
            == ['8C', '8S', 'TC', 'TD', 'TH'])
    assert (sorted(best_hand("JD TC TH 7C 7D 7S 7H".split()))
            == ['7C', '7D', '7H', '7S', 'JD'])
    print('OK')


def test_best_wild_hand():
    print("test_best_wild_hand...")
    assert (sorted(best_wild_hand("6C 7C 8C 9C TC 5C ?B".split()))
            == ['7C', '8C', '9C', 'JC', 'TC'])
    assert (sorted(best_wild_hand("TD TC 5H 5C 7C ?R ?B".split()))
            == ['7C', 'TC', 'TD', 'TH', 'TS'])
    assert (sorted(best_wild_hand("JD TC TH 7C 7D 7S 7H".split()))
            == ['7C', '7D', '7H', '7S', 'JD'])
    print('OK')


if __name__ == '__main__':
    test_best_hand()
    test_best_wild_hand()
