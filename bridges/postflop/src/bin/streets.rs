// SPDX-License-Identifier: AGPL-3.0-or-later
//
// showdown's turn and river bridge to b-inary's postflop-solver (DECISIONS 44). Like the flop
// bridge in src/main.rs, it reads one spot as JSON on stdin and writes one result as JSON on
// stdout, but it starts from the turn (4 board cards) or the river (5), and takes each range as
// 1,326 raw weights in the solver's combo order. This program links AGPL-3.0 code; showdown
// runs it only as a separate process (DECISIONS 29).
use postflop_solver::*;
use serde_json::{json, Value};
use std::io::Read;
use std::time::Instant;

fn label_matches(label: &str, action: &Action) -> bool {
    matches!(
        (label, action),
        ("Fold", Action::Fold)
            | ("Check", Action::Check)
            | ("Call", Action::Call)
            | ("Bet", Action::Bet(_))
            | ("Raise", Action::Raise(_))
            | ("AllIn", Action::AllIn(_))
    )
}

/// Moves to the node at `path`; false if the path leaves the tree or ends off a decision node.
fn walk(game: &mut PostFlopGame, path: &[String]) -> bool {
    game.back_to_root();
    for label in path {
        if game.is_terminal_node() || game.is_chance_node() {
            return false;
        }
        let actions = game.available_actions();
        match actions.iter().position(|a| label_matches(label, a)) {
            Some(i) => game.play(i),
            None => return false,
        }
    }
    !game.is_terminal_node() && !game.is_chance_node()
}

fn main() {
    let start = Instant::now();
    let mut input = String::new();
    std::io::stdin().read_to_string(&mut input).unwrap();
    let spec: Value = serde_json::from_str(&input).unwrap();
    let text = |key: &str| spec[key].as_str().unwrap().to_string();
    let sizes = |bet: &str, raise: &str| BetSizeOptions::try_from((bet, raise)).unwrap();
    let range = |key: &str| {
        let raw: Vec<f32> =
            spec[key].as_array().unwrap().iter().map(|v| v.as_f64().unwrap() as f32).collect();
        Range::from_raw_data(&raw).unwrap()
    };

    let board = text("board");
    let cards: Vec<Card> =
        (0..board.len()).step_by(2).map(|i| card_from_str(&board[i..i + 2]).unwrap()).collect();
    let (initial_state, river) = match cards.len() {
        4 => (BoardState::Turn, NOT_DEALT),
        5 => (BoardState::River, cards[4]),
        n => panic!("the board must have 4 or 5 cards, not {n}"),
    };
    let card_config = CardConfig {
        range: [range("oop_range"), range("ip_range")],
        flop: [cards[0], cards[1], cards[2]],
        turn: cards[3],
        river,
    };

    let starting_pot = spec["starting_pot"].as_i64().unwrap() as i32;
    let turn = sizes(&text("turn_bet"), &text("turn_raise"));
    let oop_turn = match spec["oop_turn_bet"].as_str() {
        Some(bet) => sizes(bet, &text("turn_raise")),
        None => turn.clone(),
    };
    let river_sizes = sizes(&text("river_bet"), &text("river_raise"));
    let tree_config = TreeConfig {
        initial_state,
        starting_pot,
        effective_stack: spec["effective_stack"].as_i64().unwrap() as i32,
        rake_rate: 0.0,
        rake_cap: 0.0,
        flop_bet_sizes: [turn.clone(), turn.clone()], // unused: the tree starts after the flop
        turn_bet_sizes: [oop_turn, turn],
        river_bet_sizes: [river_sizes.clone(), river_sizes],
        turn_donk_sizes: Some(DonkSizeOptions { donk: vec![] }),
        river_donk_sizes: Some(DonkSizeOptions::try_from(text("river_donk").as_str()).unwrap()),
        add_allin_threshold: 1.5,
        force_allin_threshold: 0.15,
        merging_threshold: 0.1,
    };
    let action_tree = ActionTree::new(tree_config).unwrap();
    let mut game = PostFlopGame::with_config(card_config, action_tree).unwrap();
    let (memory, _) = game.memory_usage();
    let memory_gb = memory as f64 / 1e9;
    let compressed = memory_gb > spec["compress_over_gb"].as_f64().unwrap_or(10.0);
    game.allocate_memory(compressed);
    let build_s = start.elapsed().as_secs_f64();

    // postflop_solver::solve's loop, kept here to report the iteration count.
    let target = starting_pot as f32 * spec["target_pct"].as_f64().unwrap() as f32 / 100.0;
    let max_iterations = spec["max_iterations"].as_u64().unwrap() as u32;
    let mut exploitability = compute_exploitability(&game);
    let mut iterations = 0;
    for t in 0..max_iterations {
        if exploitability <= target {
            break;
        }
        solve_step(&game, t);
        iterations = t + 1;
        if (t + 1) % 10 == 0 || t + 1 == max_iterations {
            exploitability = compute_exploitability(&game);
        }
    }
    finalize(&mut game);
    let solve_s = start.elapsed().as_secs_f64() - build_s;

    game.back_to_root();
    game.cache_normalized_weights();
    let mut root_ev = Vec::new();
    for player in 0..2 {
        let ev = game.expected_values(player);
        let w = game.normalized_weights(player);
        let total: f64 = w.iter().map(|&x| x as f64).sum();
        let avg: f64 = ev.iter().zip(w).map(|(&e, &x)| e as f64 * x as f64).sum::<f64>() / total;
        root_ev.push(avg);
    }

    let mut reports = Vec::new();
    for path in spec["report"].as_array().cloned().unwrap_or_default() {
        let path: Vec<String> =
            path.as_array().unwrap().iter().map(|v| v.as_str().unwrap().to_string()).collect();
        if !walk(&mut game, &path) {
            reports.push(json!({ "path": path, "reached": false }));
            continue;
        }
        game.cache_normalized_weights();
        let player = game.current_player();
        reports.push(json!({
            "path": path,
            "reached": true,
            "player": player,
            "actions": game.available_actions().iter().map(|a| format!("{a:?}")).collect::<Vec<_>>(),
            "hands": holes_to_strings(game.private_cards(player)).unwrap(),
            "weights": game.normalized_weights(player).to_vec(),
            "equity": game.equity(player),
            "strategy": game.strategy(),
        }));
    }

    let result = json!({
        "memory_gb": memory_gb,
        "compressed": compressed,
        "build_s": build_s,
        "solve_s": solve_s,
        "iterations": iterations,
        "exploitability": exploitability,
        "exploitability_pct": 100.0 * exploitability as f64 / starting_pot as f64,
        "root_ev": root_ev,
        "reports": reports,
    });
    println!("{result}");
}
