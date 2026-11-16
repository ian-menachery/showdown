// SPDX-License-Identifier: AGPL-3.0-or-later
//
// showdown's bridge to b-inary's postflop-solver (DECISIONS 38, 40). Reads one spot as JSON on
// stdin and writes one result as JSON on stdout. See README.md for the protocol. This program
// links AGPL-3.0 code; showdown runs it only as a separate process (DECISIONS 29).
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

fn find_action(actions: &[Action], label: &str) -> usize {
    actions
        .iter()
        .position(|a| label_matches(label, a))
        .unwrap_or_else(|| panic!("action {label} is not available here: {actions:?}"))
}

fn labels(path: &Value) -> Vec<String> {
    path.as_array().unwrap().iter().map(|v| v.as_str().unwrap().to_string()).collect()
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

fn names(actions: &[Action]) -> Vec<String> {
    actions.iter().map(|a| format!("{a:?}")).collect()
}

fn hands(game: &PostFlopGame, player: usize) -> Vec<String> {
    holes_to_strings(game.private_cards(player)).unwrap()
}

fn lock_vector(
    rule: &str,
    fraction: f64,
    actions: &[Action],
    root_equity: &[f32],
    root_weights: &[f32],
) -> Vec<f32> {
    let n = root_equity.len();
    let mut lock = vec![0.0f32; actions.len() * n];
    match rule {
        "call" | "check" | "bet" => {
            let label = match rule {
                "call" => "Call",
                "check" => "Check",
                _ => "Bet",
            };
            let a = find_action(actions, label);
            for h in 0..n {
                lock[a * n + h] = 1.0;
            }
        }
        "fold_weakest" => {
            let (fold, call) = (find_action(actions, "Fold"), find_action(actions, "Call"));
            let mut order: Vec<usize> = (0..n).collect();
            order.sort_by(|&a, &b| root_equity[a].partial_cmp(&root_equity[b]).unwrap());
            let total: f64 = root_weights.iter().map(|&w| w as f64).sum();
            let mut taken = 0.0f64;
            for &h in &order {
                let a = if taken < fraction * total { fold } else { call };
                lock[a * n + h] = 1.0;
                taken += root_weights[h] as f64;
            }
        }
        _ => panic!("unknown lock rule {rule}"),
    }
    lock
}

fn main() {
    let start = Instant::now();
    let mut input = String::new();
    std::io::stdin().read_to_string(&mut input).unwrap();
    let spec: Value = serde_json::from_str(&input).unwrap();
    let text = |key: &str| spec[key].as_str().unwrap().to_string();
    let sizes = |bet: &str, raise: &str| {
        BetSizeOptions::try_from((text(bet).as_str(), text(raise).as_str())).unwrap()
    };
    let card_config = CardConfig {
        range: [text("oop_range").parse().unwrap(), text("ip_range").parse().unwrap()],
        flop: flop_from_str(&text("flop")).unwrap(),
        turn: NOT_DEALT,
        river: NOT_DEALT,
    };
    let starting_pot = spec["starting_pot"].as_i64().unwrap() as i32;
    let (flop, turn, river) = (
        sizes("flop_bet", "flop_raise"),
        sizes("turn_bet", "turn_raise"),
        sizes("river_bet", "river_raise"),
    );
    let tree_config = TreeConfig {
        initial_state: BoardState::Flop,
        starting_pot,
        effective_stack: spec["effective_stack"].as_i64().unwrap() as i32,
        rake_rate: 0.0,
        rake_cap: 0.0,
        flop_bet_sizes: [flop.clone(), flop],
        turn_bet_sizes: [turn.clone(), turn],
        river_bet_sizes: [river.clone(), river],
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

    // Flop equity against the opponent's whole range, before any strategy: ranks hands for locks.
    game.cache_normalized_weights();
    let root_equity = [game.equity(0), game.equity(1)];
    let root_weights = [game.normalized_weights(0).to_vec(), game.normalized_weights(1).to_vec()];

    let mut applied = Vec::new();
    for lock in spec["locks"].as_array().cloned().unwrap_or_default() {
        let path = labels(&lock["path"]);
        if !walk(&mut game, &path) {
            panic!("lock path {path:?} is not a decision node");
        }
        let player = game.current_player();
        let actions = game.available_actions();
        let vector = lock_vector(
            lock["rule"].as_str().unwrap(),
            lock["fraction"].as_f64().unwrap_or(0.0),
            &actions,
            &root_equity[player],
            &root_weights[player],
        );
        game.lock_current_strategy(&vector);
        applied.push(json!({
            "path": path, "player": player, "actions": names(&actions),
            "hands": hands(&game, player), "strategy": vector,
        }));
    }
    game.back_to_root();
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
        let path = labels(&path);
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
            "actions": names(&game.available_actions()),
            "hands": hands(&game, player),
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
        "locks": applied,
        "reports": reports,
    });
    println!("{result}");
}
