"""
Web Dashboard for Twitter / X Multi-Account Command Center (Unified Multi-Account Edition)
Prinsip:
- SEMUA FITUR BERLAKU UNTUK SEMUA AKUN (Tidak ada lagi istilah Akun Utama vs Akun Farm).
- Setiap akun memiliki sesi autentikasi (auth_token & ct0) dan alamat wallet (EVM & Solana) masing-masing.
- Setiap akun dapat menjalankan:
  1. Yapping Random (Post yapping santai + 5x like & smart comment) secara looping terus-menerus (jeda 10-30 menit per siklus).
  2. Scraping Giveaway (Auto Like, Retweet, Follow, dan Drop Address milik akun itu sendiri) secara looping (jeda 10-30 menit).
- Left Sidebar Navbar dengan 4 Menu:
  1. Dashboard: Tambah & Kelola Semua Akun Twitter.
  2. Yapping Random: Pemanasan & Interaksi Semua Akun (Looping 10-30m).
  3. Scraping Giveaway: Perburuan Giveaway Semua Akun (Looping 10-30m).
  4. Submit Address: Input Alamat EVM (0x...) & Solana (Base58) per-akun.
"""

import asyncio
import json
import logging
import os
import random
import sys
from datetime import datetime
from pathlib import Path
from aiohttp import web

# Terminal utf-8 support for Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
        sys.stderr.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    except Exception:
        pass

from config import ACCOUNTS_FILE, COOKIES_FILE, RESULTS_DIR
from accounts_manager import (
    load_accounts, 
    save_accounts, 
    switch_account, 
    add_account, 
    remove_account, 
    get_active_account,
    verify_tokens_with_browser
)
from wallet_config import (
    load_wallet_config, 
    save_wallet_config, 
    is_valid_evm_address, 
    is_valid_solana_address
)

CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
MAGENTA = "\033[95m"
RESET = "\033[0m"

logger = logging.getLogger(__name__)

WARMUP_HISTORY_FILE = RESULTS_DIR / "warmup_history.json"
AIRDROP_HISTORY_FILE = RESULTS_DIR / "airdrop_history.json"

# State running tasks: { "username_lower": asyncio.Task }
RUNNING_WARM_TASKS = {}
WARM_ACCOUNTS_STATE = {}

RUNNING_HUNTER_TASKS = {}
HUNTER_ACCOUNTS_STATE = {}


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="id">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>𝕏 Command Center & Multi-Account Suite</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg: #0b0f19;
      --sidebar-bg: #0e1526;
      --card-bg: rgba(18, 26, 43, 0.75);
      --card-border: rgba(255, 255, 255, 0.08);
      --card-hover: rgba(255, 255, 255, 0.14);
      --primary: #3b82f6;
      --primary-glow: rgba(59, 130, 246, 0.35);
      --accent: #10b981;
      --accent-glow: rgba(16, 185, 129, 0.3);
      --solana: #a855f7;
      --solana-glow: rgba(168, 85, 247, 0.3);
      --warning: #f59e0b;
      --danger: #ef4444;
      --text: #f3f4f6;
      --text-muted: #94a3b8;
      --mono: 'JetBrains Mono', monospace;
    }

    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background-color: var(--bg);
      background-image: 
        radial-gradient(at 0% 0%, rgba(59, 130, 246, 0.09) 0px, transparent 50%),
        radial-gradient(at 100% 100%, rgba(168, 85, 247, 0.07) 0px, transparent 50%);
      color: var(--text);
      font-family: 'Plus Jakarta Sans', sans-serif;
      min-height: 100vh;
      line-height: 1.5;
      display: flex;
    }

    /* LEFT SIDEBAR NAVBAR */
    .sidebar {
      position: fixed;
      top: 0;
      left: 0;
      bottom: 0;
      width: 270px;
      background: var(--sidebar-bg);
      border-right: 1px solid var(--card-border);
      padding: 24px 16px;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      z-index: 1000;
      backdrop-filter: blur(24px);
      box-shadow: 4px 0 24px rgba(0,0,0,0.35);
    }

    .brand {
      display: flex;
      align-items: center;
      gap: 12px;
      padding-bottom: 24px;
      border-bottom: 1px solid var(--card-border);
      margin-bottom: 20px;
    }

    .logo-icon {
      width: 44px;
      height: 44px;
      background: linear-gradient(135deg, #1d9bf0, #a855f7);
      border-radius: 12px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 22px;
      font-weight: 800;
      box-shadow: 0 4px 16px var(--primary-glow);
    }

    .brand-text h1 {
      font-size: 18px;
      font-weight: 800;
      letter-spacing: -0.5px;
      color: #ffffff;
      line-height: 1.2;
    }

    .brand-text p {
      color: var(--text-muted);
      font-size: 12px;
      margin-top: 2px;
    }

    .nav-menu {
      display: flex;
      flex-direction: column;
      gap: 8px;
      flex: 1;
    }

    .nav-label {
      font-size: 11px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.8px;
      color: var(--text-muted);
      margin: 12px 10px 4px 10px;
    }

    .nav-item {
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 12px 16px;
      border-radius: 12px;
      color: var(--text-muted);
      text-decoration: none;
      font-weight: 600;
      font-size: 13.5px;
      cursor: pointer;
      transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
      border: 1px solid transparent;
      user-select: none;
    }

    .nav-item .icon {
      font-size: 18px;
      line-height: 1;
    }

    .nav-item:hover {
      color: #ffffff;
      background: rgba(255, 255, 255, 0.05);
      border-color: rgba(255, 255, 255, 0.08);
      transform: translateX(3px);
    }

    .nav-item.active {
      background: linear-gradient(135deg, rgba(59, 130, 246, 0.22), rgba(168, 85, 247, 0.16));
      border: 1px solid rgba(59, 130, 246, 0.5);
      color: #ffffff;
      box-shadow: 0 4px 16px var(--primary-glow);
    }

    .sidebar-footer {
      padding-top: 18px;
      border-top: 1px solid var(--card-border);
      display: flex;
      flex-direction: column;
      gap: 10px;
    }

    .system-status {
      display: flex;
      align-items: center;
      justify-content: space-between;
      background: rgba(255, 255, 255, 0.03);
      padding: 10px 12px;
      border-radius: 10px;
      font-size: 12px;
      border: 1px solid var(--card-border);
    }

    .status-dot {
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: #10b981;
      display: inline-block;
      box-shadow: 0 0 8px #10b981;
      animation: pulse 2s infinite;
    }

    @keyframes pulse {
      0% { opacity: 1; transform: scale(1); }
      50% { opacity: 0.5; transform: scale(0.9); }
      100% { opacity: 1; transform: scale(1); }
    }

    /* MAIN CONTENT AREA */
    .main-wrapper {
      margin-left: 270px;
      flex: 1;
      padding: 30px 40px;
      min-height: 100vh;
      max-width: 1400px;
    }

    .page-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 24px;
      flex-wrap: wrap;
      gap: 16px;
    }

    .page-title h2 {
      font-size: 24px;
      font-weight: 800;
      letter-spacing: -0.5px;
      color: #ffffff;
      display: flex;
      align-items: center;
      gap: 10px;
    }

    .page-title p {
      color: var(--text-muted);
      font-size: 13.5px;
      margin-top: 4px;
    }

    .tab-content {
      display: none;
      animation: fadeIn 0.25s ease-out forwards;
    }

    .tab-content.active {
      display: block;
    }

    @keyframes fadeIn {
      from { opacity: 0; transform: translateY(6px); }
      to { opacity: 1; transform: translateY(0); }
    }

    /* Stats Grid */
    .stats-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
      gap: 16px;
      margin-bottom: 24px;
    }

    .stat-card {
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 14px;
      padding: 18px 20px;
      backdrop-filter: blur(16px);
      transition: all 0.2s ease;
    }
    .stat-card:hover {
      border-color: var(--card-hover);
      transform: translateY(-2px);
    }

    .stat-label {
      color: var(--text-muted);
      font-size: 12px;
      font-weight: 700;
      margin-bottom: 6px;
      text-transform: uppercase;
      letter-spacing: 0.6px;
    }

    .stat-value {
      font-size: 26px;
      font-weight: 800;
      letter-spacing: -0.5px;
    }

    .stat-sub {
      color: var(--text-muted);
      font-size: 12px;
      margin-top: 4px;
    }

    /* Panels */
    .panel {
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 16px;
      padding: 24px;
      backdrop-filter: blur(16px);
      margin-bottom: 24px;
    }

    .panel-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 20px;
      flex-wrap: wrap;
      gap: 12px;
    }

    .panel-title {
      font-size: 17px;
      font-weight: 700;
      display: flex;
      align-items: center;
      gap: 10px;
      color: #ffffff;
    }

    .panel-subtitle {
      color: var(--text-muted);
      font-size: 13px;
      margin-top: 2px;
    }

    /* Buttons */
    .btn {
      padding: 8px 15px;
      border-radius: 9px;
      font-weight: 600;
      font-size: 13px;
      cursor: pointer;
      border: 1px solid transparent;
      display: inline-flex;
      align-items: center;
      gap: 6px;
      transition: all 0.2s ease;
      text-decoration: none;
      line-height: 1.4;
      white-space: nowrap;
    }

    .btn:active {
      transform: scale(0.98);
    }

    .btn-primary {
      background: linear-gradient(135deg, #3b82f6, #2563eb);
      color: white;
      box-shadow: 0 4px 14px var(--primary-glow);
    }
    .btn-primary:hover {
      background: linear-gradient(135deg, #60a5fa, #3b82f6);
    }

    .btn-start {
      background: linear-gradient(135deg, #10b981, #059669);
      color: white;
      box-shadow: 0 3px 12px var(--accent-glow);
      font-weight: 700;
    }
    .btn-start:hover {
      background: linear-gradient(135deg, #34d399, #10b981);
    }

    .btn-hunter {
      background: linear-gradient(135deg, #8b5cf6, #6366f1);
      color: white;
      box-shadow: 0 3px 12px var(--solana-glow);
      font-weight: 700;
    }
    .btn-hunter:hover {
      background: linear-gradient(135deg, #a855f7, #8b5cf6);
    }

    .btn-stop {
      background: rgba(239, 68, 68, 0.15);
      border: 1px solid rgba(239, 68, 68, 0.45);
      color: #ef4444;
      font-weight: 700;
    }
    .btn-stop:hover {
      background: rgba(239, 68, 68, 0.28);
      border-color: rgba(239, 68, 68, 0.65);
    }

    .btn-danger {
      background: rgba(239, 68, 68, 0.15);
      border: 1px solid rgba(239, 68, 68, 0.45);
      color: #fca5a5;
    }
    .btn-danger:hover {
      background: rgba(239, 68, 68, 0.3);
      color: white;
    }

    .btn-outline {
      background: rgba(255, 255, 255, 0.05);
      border: 1px solid var(--card-border);
      color: var(--text);
    }
    .btn-outline:hover {
      background: rgba(255, 255, 255, 0.1);
      border-color: rgba(255, 255, 255, 0.2);
    }

    /* Forms & Inputs */
    .form-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
      gap: 16px;
    }

    .form-group {
      display: flex;
      flex-direction: column;
      gap: 6px;
    }

    .form-label {
      font-size: 13px;
      font-weight: 600;
      color: var(--text-muted);
    }

    .form-control {
      background: rgba(11, 15, 25, 0.8);
      border: 1px solid var(--card-border);
      border-radius: 9px;
      padding: 10px 14px;
      color: white;
      font-family: inherit;
      font-size: 13.5px;
      transition: all 0.2s ease;
      width: 100%;
    }

    .form-control:focus {
      outline: none;
      border-color: #3b82f6;
      box-shadow: 0 0 12px var(--primary-glow);
    }

    .form-control.mono {
      font-family: var(--mono);
      font-size: 12.5px;
    }

    /* Tables */
    .table-container {
      overflow-x: auto;
    }

    .data-table {
      width: 100%;
      border-collapse: collapse;
      text-align: left;
    }

    .data-table th {
      padding: 12px 16px;
      color: var(--text-muted);
      font-size: 12px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.6px;
      border-bottom: 1px solid var(--card-border);
    }

    .data-table td {
      padding: 14px 16px;
      border-bottom: 1px solid rgba(255, 255, 255, 0.04);
      font-size: 13.5px;
      vertical-align: middle;
    }

    .data-table tr:hover td {
      background: rgba(255, 255, 255, 0.02);
    }

    /* Badges */
    .badge {
      display: inline-flex;
      align-items: center;
      gap: 5px;
      padding: 3px 8px;
      border-radius: 6px;
      font-size: 11.5px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.3px;
    }

    .badge-primary {
      background: rgba(59, 130, 246, 0.15);
      color: #60a5fa;
      border: 1px solid rgba(59, 130, 246, 0.3);
    }

    .badge-success {
      background: rgba(16, 185, 129, 0.15);
      color: #34d399;
      border: 1px solid rgba(16, 185, 129, 0.3);
    }

    .badge-warning {
      background: rgba(245, 158, 11, 0.15);
      color: #fbbf24;
      border: 1px solid rgba(245, 158, 11, 0.3);
    }

    .badge-sol {
      background: rgba(168, 85, 247, 0.15);
      color: #c084fc;
      border: 1px solid rgba(168, 85, 247, 0.3);
    }

    .badge-evm {
      background: rgba(59, 130, 246, 0.15);
      color: #93c5fd;
      border: 1px solid rgba(59, 130, 246, 0.3);
    }

    .account-meta {
      display: flex;
      align-items: center;
      gap: 10px;
    }

    .account-avatar {
      width: 38px;
      height: 38px;
      border-radius: 50%;
      background: linear-gradient(135deg, rgba(255,255,255,0.1), rgba(255,255,255,0.02));
      border: 1px solid var(--card-border);
      display: flex;
      align-items: center;
      justify-content: center;
      font-weight: 700;
      font-size: 14px;
      color: #ffffff;
      flex-shrink: 0;
    }

    .grid-2col {
      display: grid;
      grid-template-columns: 2fr 1fr;
      gap: 24px;
    }

    @media (max-width: 1100px) {
      .grid-2col {
        grid-template-columns: 1fr;
      }
    }

    .feed-list {
      display: flex;
      flex-direction: column;
      gap: 10px;
      max-height: 580px;
      overflow-y: auto;
      padding-right: 6px;
    }

    .feed-item {
      background: rgba(255, 255, 255, 0.02);
      border: 1px solid var(--card-border);
      border-radius: 10px;
      padding: 12px 14px;
      font-size: 13px;
    }

    .feed-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 6px;
    }

    .feed-content {
      color: var(--text);
      line-height: 1.4;
      font-family: var(--mono);
      font-size: 12px;
      word-break: break-word;
    }

    .toast-box {
      position: fixed;
      bottom: 24px;
      right: 24px;
      background: #1e293b;
      border: 1px solid #3b82f6;
      border-radius: 10px;
      padding: 14px 20px;
      font-size: 13px;
      color: white;
      box-shadow: 0 10px 30px rgba(0,0,0,0.5);
      display: none;
      z-index: 9999;
      animation: toastIn 0.2s ease-out;
    }

    @keyframes toastIn {
      from { transform: translateY(10px); opacity: 0; }
      to { transform: translateY(0); opacity: 1; }
    }
  </style>
</head>
<body>

  <div class="toast-box" id="toast"></div>

  <!-- SIDEBAR NAVBAR -->
  <aside class="sidebar">
    <div>
      <div class="brand">
        <div class="logo-icon">𝕏</div>
        <div class="brand-text">
          <h1>Command Center</h1>
          <p>Multi-Account Twitter Suite</p>
        </div>
      </div>

      <div class="nav-label">Navigasi Fitur</div>
      <nav class="nav-menu">
        <div class="nav-item active" id="nav-dashboard" onclick="switchMenu('dashboard')">
          <span class="icon">📊</span>
          <span>Dashboard</span>
        </div>
        <div class="nav-item" id="nav-yapping" onclick="switchMenu('yapping')">
          <span class="icon">💬</span>
          <span>Yapping Random</span>
        </div>
        <div class="nav-item" id="nav-giveaway" onclick="switchMenu('giveaway')">
          <span class="icon">🎁</span>
          <span>Scraping Giveaway</span>
        </div>
        <div class="nav-item" id="nav-wallets" onclick="switchMenu('wallets')">
          <span class="icon">👛</span>
          <span>Submit Address</span>
        </div>
      </nav>
    </div>

    <div class="sidebar-footer">
      <div class="system-status">
        <div style="display: flex; align-items: center; gap: 8px;">
          <span class="status-dot"></span>
          <span>Server: :5050</span>
        </div>
        <span style="color: #10b981; font-weight: 700;">Online</span>
      </div>
      <button class="btn btn-outline" style="width: 100%; justify-content: center;" onclick="refreshAll()">
        🔄 Refresh Semua Data
      </button>
    </div>
  </aside>

  <!-- MAIN WRAPPER -->
  <main class="main-wrapper">

    <!-- ===================================================================== -->
    <!-- MENU 1: DASHBOARD (TAMBAH & KELOLA SEMUA AKUN)                         -->
    <!-- ===================================================================== -->
    <section id="tab-dashboard" class="tab-content active">
      <div class="page-header">
        <div class="page-title">
          <h2>📊 Dashboard &amp; Kelola Akun Twitter</h2>
          <p>Daftar semua akun Twitter. Tambahkan akun baru via auth_token &amp; ct0, pantau interaksi, atau hapus akun.</p>
        </div>
      </div>

      <!-- Stats Overview Grid -->
      <div class="stats-grid">
        <div class="stat-card">
          <div class="stat-label">Total Akun Terdaftar</div>
          <div class="stat-value" id="dash-total-accounts">-</div>
          <div class="stat-sub">Semua Akun Siap Dijalankan</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">Total Post Yapping</div>
          <div class="stat-value" style="color: #60a5fa;" id="dash-total-posts">-</div>
          <div class="stat-sub">Akumulasi Semua Akun</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">Total Like &amp; Komentar</div>
          <div class="stat-value" style="color: #10b981;" id="dash-total-comments">-</div>
          <div class="stat-sub">Akumulasi Interaksi Semua Akun</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">Total Giveaway Diikuti</div>
          <div class="stat-value" style="color: #c084fc;" id="dash-total-airdrop">-</div>
          <div class="stat-sub">Tercatat di airdrop history</div>
        </div>
      </div>

      <!-- Form Tambah Akun Baru -->
      <div class="panel">
        <div class="panel-header">
          <div>
            <div class="panel-title">➕ Tambah Akun Twitter Baru</div>
            <div class="panel-subtitle">Ambil auth_token dan ct0 dari Cookies browser Chrome (F12 > Application > Cookies > x.com).</div>
          </div>
        </div>

        <form id="form-add-account" onsubmit="submitAddAccount(event)">
          <div class="form-grid">
            <div class="form-group">
              <label class="form-label">auth_token <span style="color: #ef4444;">*</span></label>
              <input type="text" class="form-control mono" id="input-auth-token" placeholder="Contoh: 82fe4a33a6343336a9038b8..." required>
            </div>
            <div class="form-group">
              <label class="form-label">ct0 <span style="color: #ef4444;">*</span></label>
              <input type="text" class="form-control mono" id="input-ct0" placeholder="Contoh: d5d70bdb1b27ea89f7d209..." required>
            </div>
            <div class="form-group">
              <label class="form-label">Username / Screen Name <span style="color: var(--text-muted);">(Opsional)</span></label>
              <input type="text" class="form-control" id="input-screen-name" placeholder="Contoh: @username_kamu (Kosongkan jika auto-detect)">
            </div>
            <div class="form-group">
              <label class="form-label">Display Name <span style="color: var(--text-muted);">(Opsional)</span></label>
              <input type="text" class="form-control" id="input-display-name" placeholder="Contoh: Nama Tampilan">
            </div>
          </div>

          <div style="display: flex; justify-content: flex-end; align-items: center; margin-top: 16px;">
            <button type="submit" class="btn btn-primary" id="btn-submit-account">
              ➕ Simpan &amp; Tambahkan Akun
            </button>
          </div>
        </form>
      </div>

      <!-- Tabel Daftar Semua Akun -->
      <div class="panel">
        <div class="panel-header">
          <div>
            <div class="panel-title">👥 Daftar Semua Akun Twitter</div>
            <div class="panel-subtitle">Semua akun setara dan dapat digunakan untuk yapping, scraping giveaway, dan wallet submission.</div>
          </div>
        </div>

        <div class="table-container">
          <table class="data-table">
            <thead>
              <tr>
                <th>Akun Twitter</th>
                <th>Status Akun</th>
                <th>Token Preview</th>
                <th>Ditambahkan</th>
                <th style="width: 100px; text-align: center;">Aksi</th>
              </tr>
            </thead>
            <tbody id="dash-accounts-tbody">
              <!-- Rendered via JS -->
            </tbody>
          </table>
        </div>
      </div>
    </section>


    <!-- ===================================================================== -->
    <!-- MENU 2: YAPPING RANDOM (PEMANASAN SEMUA AKUN)                         -->
    <!-- ===================================================================== -->
    <section id="tab-yapping" class="tab-content">
      <div class="page-header">
        <div class="page-title">
          <h2>💬 Yapping Random (Pemanasan &amp; Interaksi)</h2>
          <p>Fitur berlaku untuk semua akun: Satu kali klik "Start" langsung memposting tweet yapping natural &amp; 5x like komentar tanpa retweet secara looping terus-menerus (jeda 10-30 menit per siklus).</p>
        </div>
        <div style="display: flex; gap: 10px;">
          <button class="btn btn-start" onclick="startAllYapping()">▶️ Mulai Semua Akun</button>
          <button class="btn btn-stop" onclick="stopAllYapping()">⏹️ Hentikan Semua</button>
        </div>
      </div>

      <!-- Stats Pemanasan -->
      <div class="stats-grid">
        <div class="stat-card">
          <div class="stat-label">Total Postingan Yapping</div>
          <div class="stat-value" style="color: #60a5fa;" id="yap-total-posts">-</div>
          <div class="stat-sub">Bahasa Indo &amp; Anti-Duplikasi</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">Total Like &amp; Komentar</div>
          <div class="stat-value" style="color: #a78bfa;" id="yap-total-comments">-</div>
          <div class="stat-sub">5x Interaksi Tiap Siklus</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">Akun Sedang Yapping</div>
          <div class="stat-value" style="color: #10b981;" id="yap-running-count">0</div>
          <div class="stat-sub">Tugas aktif looping</div>
        </div>
      </div>

      <div class="grid-2col">
        <!-- Kolom Kiri: Tabel Kontrol Yapping Semua Akun -->
        <div>
          <div class="panel">
            <div class="panel-header">
              <div>
                <div class="panel-title">⚡ Kontrol Yapping Semua Akun</div>
                <div class="panel-subtitle">Setiap akun berjalan mandiri dalam loop dengan jeda 10-30 menit antar siklus sampai dihentikan manual.</div>
              </div>
            </div>

            <div class="table-container">
              <table class="data-table">
                <thead>
                  <tr>
                    <th>Akun</th>
                    <th>Status Looping</th>
                    <th>Post</th>
                    <th>Interaksi</th>
                    <th>Aksi Kontrol</th>
                  </tr>
                </thead>
                <tbody id="yapping-accounts-tbody">
                  <!-- Rendered via JS -->
                </tbody>
              </table>
            </div>
          </div>
        </div>

        <!-- Kolom Kanan: Live Activity Feed -->
        <div>
          <div class="panel">
            <div class="panel-header">
              <div class="panel-title">📜 Aktivitas Warming Up Terkini</div>
            </div>
            <div class="feed-list" id="activity-feed">
              <div style="color: var(--text-muted); text-align: center; padding: 20px;">Memuat riwayat...</div>
            </div>
          </div>
        </div>
      </div>
    </section>


    <!-- ===================================================================== -->
    <!-- MENU 3: SCRAPING GIVEAWAY (BERLAKU UNTUK SEMUA AKUN)                  -->
    <!-- ===================================================================== -->
    <section id="tab-giveaway" class="tab-content">
      <div class="page-header">
        <div class="page-title">
          <h2>🎁 Scraping Giveaway &amp; Auto-Drop Address</h2>
          <p>Fitur ini berlaku untuk semua akun! Setiap akun dapat memindai giveaway, like, retweet, follow, dan mendrop alamat wallet miliknya sendiri secara looping (jeda 10-30 menit).</p>
        </div>
        <div style="display: flex; gap: 10px;">
          <button class="btn btn-hunter" onclick="startAllHunter()">🚀 Mulai Scraping Semua Akun</button>
          <button class="btn btn-stop" onclick="stopAllHunter()">⏹️ Hentikan Semua</button>
        </div>
      </div>

      <!-- Pengaturan Global Scraping -->
      <div class="panel">
        <div class="panel-header">
          <div>
            <div class="panel-title">⚙️ Konfigurasi Target Scraping</div>
            <div class="panel-subtitle">Atur filter jaringan dan kuota tweet target yang berlaku saat memindai giveaway.</div>
          </div>
        </div>

        <div style="display: flex; gap: 20px; align-items: flex-end; flex-wrap: wrap;">
          <div class="form-group" style="min-width: 240px;">
            <label class="form-label">Kategori / Jaringan:</label>
            <select class="form-control" id="select-category">
              <option value="ALL">🌐 Semua Jaringan (EVM &amp; Solana)</option>
              <option value="EVM">🦊 EVM Only (ETH, BSC, Base, Arbitrum)</option>
              <option value="SOLANA">🟣 Solana Only (SOL, Phantom)</option>
            </select>
          </div>

          <div class="form-group" style="min-width: 200px;">
            <label class="form-label">Jumlah Target Tweet Per Siklus:</label>
            <select class="form-control" id="select-count">
              <option value="5">5 Tweet Giveaway</option>
              <option value="10" selected>10 Tweet Giveaway</option>
              <option value="20">20 Tweet Giveaway</option>
              <option value="35">35 Tweet Giveaway</option>
            </select>
          </div>

          <div style="color: var(--text-muted); font-size: 13px; max-width: 450px;">
            ℹ️ Setiap siklus scraping akan berhenti sejenak selama <strong>10–30 menit</strong> sebelum memindai gelombang giveaway baru secara otomatis.
          </div>
        </div>
      </div>

      <!-- Tabel Kontrol Scraping Giveaway Semua Akun -->
      <div class="panel">
        <div class="panel-header">
          <div>
            <div class="panel-title">👥 Kontrol Scraping Giveaway Per-Akun</div>
            <div class="panel-subtitle">Jalankan scraper untuk akun tertentu atau semua akun secara bersamaan. Alamat wallet yang didrop disesuaikan dengan akun masing-masing.</div>
          </div>
        </div>

        <div class="table-container">
          <table class="data-table">
            <thead>
              <tr>
                <th>Akun Twitter</th>
                <th>Alamat Wallet Digunakan</th>
                <th>Status Looping</th>
                <th>Total Entri</th>
                <th>Aksi Scraping</th>
              </tr>
            </thead>
            <tbody id="giveaway-accounts-tbody">
              <!-- Rendered via JS -->
            </tbody>
          </table>
        </div>
      </div>

      <!-- Tabel Riwayat Entri Giveaway -->
      <div class="panel">
        <div class="panel-header">
          <div>
            <div class="panel-title">📜 Riwayat Entri Giveaway Terbaru</div>
            <div class="panel-subtitle">Daftar giveaway yang telah diikuti beserta akun yang mengeksekusinya.</div>
          </div>
          <button class="btn btn-outline" onclick="fetchAirdropHistory()">🔄 Segarkan Riwayat</button>
        </div>

        <div class="table-container">
          <table class="data-table">
            <thead>
              <tr>
                <th>Waktu</th>
                <th>Akun Eksekutor</th>
                <th>Author Host</th>
                <th>Jaringan</th>
                <th>Isi Tweet Giveaway</th>
                <th>Aksi Selesai</th>
                <th>Tautan</th>
              </tr>
            </thead>
            <tbody id="airdrop-history-tbody">
              <!-- Rendered via JS -->
            </tbody>
          </table>
        </div>
      </div>
    </section>


    <!-- ===================================================================== -->
    <!-- MENU 4: SUBMIT ADDRESS MASING-MASING AKUN                             -->
    <!-- ===================================================================== -->
    <section id="tab-wallets" class="tab-content">
      <div class="page-header">
        <div class="page-title">
          <h2>👛 Submit Address Masing-Masing Akun</h2>
          <p>Input dan kelola alamat wallet EVM (0x...) dan Solana (Base58) untuk setiap akun Twitter secara terpisah.</p>
        </div>
        <div>
          <button class="btn btn-start" onclick="saveAllWallets()">
            💾 Simpan Semua Alamat Sekaligus
          </button>
        </div>
      </div>

      <!-- Notice Panel -->
      <div class="panel" style="background: rgba(59, 130, 246, 0.08); border-color: rgba(59, 130, 246, 0.25);">
        <div style="display: flex; align-items: center; gap: 12px;">
          <span style="font-size: 24px;">💡</span>
          <div>
            <strong style="color: #60a5fa;">Informasi Alamat Wallet:</strong>
            <p style="font-size: 13px; color: var(--text-muted); margin-top: 2px;">
              Setiap akun memiliki alamat EVM dan Solana sendiri yang tersimpan di <code>accounts.json</code>.
              Saat akun tersebut menjalankan Scraping Giveaway, alamat inilah yang akan otomatis dikirimkan ke komentar host giveaway!
            </p>
          </div>
        </div>
      </div>

      <!-- Tabel Editor Wallet Per-Akun -->
      <div class="panel">
        <div class="panel-header">
          <div>
            <div class="panel-title">📝 Daftar Alamat Wallet Per-Akun</div>
            <div class="panel-subtitle">Ubah alamat EVM atau Solana pada akun terkait lalu klik "Simpan" per-akun atau "Simpan Semua Sekaligus".</div>
          </div>
        </div>

        <div class="table-container">
          <table class="data-table">
            <thead>
              <tr>
                <th style="width: 220px;">Akun Twitter</th>
                <th>Alamat EVM (0x...)</th>
                <th>Alamat Solana (Base58)</th>
                <th style="width: 130px; text-align: center;">Aksi Simpan</th>
              </tr>
            </thead>
            <tbody id="wallet-accounts-tbody">
              <!-- Rendered via JS -->
            </tbody>
          </table>
        </div>
      </div>
    </section>

  </main>


  <!-- ======================================================================= -->
  <!-- JAVASCRIPT LOGIC                                                        -->
  <!-- ======================================================================= -->
  <script>
    let GLOBAL_ACCOUNTS = [];
    let RUNNING_WARM = [];
    let RUNNING_HUNTER = [];
    let WARM_STATES = {};
    let HUNTER_STATES = {};
    let ACTIVE_ACCOUNT = '';

    // Switch Left Navbar Tabs
    function switchMenu(tabId) {
      document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));
      document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));

      const navEl = document.getElementById('nav-' + tabId);
      const tabEl = document.getElementById('tab-' + tabId);

      if (navEl) navEl.classList.add('active');
      if (tabEl) tabEl.classList.add('active');

      localStorage.setItem('active_dashboard_menu', tabId);

      if (tabId === 'giveaway') {
        fetchAirdropHistory();
      }
    }

    // Restore last active menu
    const savedMenu = localStorage.getItem('active_dashboard_menu');
    if (savedMenu && document.getElementById('tab-' + savedMenu)) {
      switchMenu(savedMenu);
    }

    function showToast(msg) {
      const t = document.getElementById('toast');
      t.innerText = msg;
      t.style.display = 'block';
      setTimeout(() => { t.style.display = 'none'; }, 4500);
    }

    function formatShortAddr(addr) {
      if (!addr) return '-';
      if (addr.length < 14) return addr;
      return addr.substring(0, 6) + '...' + addr.substring(addr.length - 4);
    }

    function censorToken(token) {
      if (!token) return '-';
      if (token.length < 12) return token;
      return token.substring(0, 6) + '...' + token.substring(token.length - 4);
    }

    async function refreshAll() {
      showToast('🔄 Memperbarui seluruh data...');
      await fetchOverview();
      await fetchAirdropHistory();
    }

    // Fetch Overview Data (Akun, Status Looping, Riwayat)
    async function fetchOverview() {
      try {
        const res = await fetch('/api/overview');
        const data = await res.json();

        GLOBAL_ACCOUNTS = data.accounts || [];
        RUNNING_WARM = data.running_warm || [];
        RUNNING_HUNTER = data.running_hunter || [];
        WARM_STATES = data.warm_states || {};
        HUNTER_STATES = data.hunter_states || {};
        ACTIVE_ACCOUNT = data.active_account || '';

        // Dashboard Stats
        document.getElementById('dash-total-accounts').innerText = data.total_accounts || 0;
        document.getElementById('dash-total-posts').innerText = data.total_yapping_posts || 0;
        document.getElementById('dash-total-comments').innerText = data.total_interactions || 0;
        document.getElementById('dash-total-airdrop').innerText = data.total_airdrop_entered || 0;

        // Yapping Stats
        document.getElementById('yap-total-posts').innerText = data.total_yapping_posts || 0;
        document.getElementById('yap-total-comments').innerText = data.total_interactions || 0;
        document.getElementById('yap-running-count').innerText = RUNNING_WARM.length;

        // Render Tab 1: Dashboard Accounts Table
        renderDashboardAccountsTable(GLOBAL_ACCOUNTS);

        // Render Tab 2: Yapping Farm Table
        renderYappingTable(GLOBAL_ACCOUNTS, RUNNING_WARM, WARM_STATES);

        // Render Tab 3: Giveaway Hunter Accounts Table
        renderGiveawayTable(GLOBAL_ACCOUNTS, RUNNING_HUNTER, HUNTER_STATES);

        // Render Tab 4: Wallet Editor Table
        renderWalletEditorTable(GLOBAL_ACCOUNTS);

        // Render Live Activity Feed
        renderActivityFeed(data.recent_activities || []);

      } catch (e) {
        console.error("Gagal memuat overview:", e);
      }
    }

    // Render Dashboard Accounts Table (Equal accounts)
    function renderDashboardAccountsTable(accounts) {
      const tbody = document.getElementById('dash-accounts-tbody');
      tbody.innerHTML = '';

      if (!accounts || accounts.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" style="text-align: center; color: var(--text-muted); padding: 24px;">Belum ada akun tersimpan. Tambahkan di form atas.</td></tr>';
        return;
      }

      accounts.forEach(acc => {
        const initial = acc.screen_name.charAt(0).toUpperCase();

        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td>
            <div class="account-meta">
              <div class="account-avatar">${initial}</div>
              <div>
                <strong style="color: #ffffff; font-size: 14px;">${acc.name || acc.screen_name}</strong>
                <div style="color: var(--text-muted); font-size: 12px;">@${acc.screen_name}</div>
              </div>
            </div>
          </td>
          <td>
            <span class="badge badge-success">🟢 Siap Digunakan</span>
          </td>
          <td>
            <div style="font-size: 11px; font-family: var(--mono); color: var(--text-muted);">
              auth: <span style="color: #93c5fd;">${censorToken(acc.auth_token)}</span><br>
              ct0: <span style="color: #c084fc;">${censorToken(acc.ct0)}</span>
            </div>
          </td>
          <td style="font-size: 12px; color: var(--text-muted);">${acc.added_at || '-'}</td>
          <td style="text-align: center;">
            <button class="btn btn-danger" style="font-size: 11px; padding: 4px 10px;" onclick="removeAccount('${acc.screen_name}')">
              🗑️ Hapus
            </button>
          </td>
        `;
        tbody.appendChild(tr);
      });
    }

    // Render Yapping Table (All accounts)
    function renderYappingTable(accounts, runningAccounts, warmStates) {
      const tbody = document.getElementById('yapping-accounts-tbody');
      tbody.innerHTML = '';
      warmStates = warmStates || {};

      if (!accounts || accounts.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" style="text-align: center; color: var(--text-muted); padding: 24px;">Belum ada akun tersimpan.</td></tr>';
        return;
      }

      accounts.forEach(acc => {
        const uLower = acc.screen_name.toLowerCase();
        const isRunning = runningAccounts.includes(uLower);
        const initial = acc.screen_name.charAt(0).toUpperCase();
        const st = warmStates[uLower] || {};

        let statusBadge = '<span class="badge badge-primary">⚪ Standby</span>';
        if (isRunning) {
          const statusText = st.status || '🟢 Aktif (Looping...)';
          statusBadge = `<span class="badge badge-warning" style="animation: pulse 1.5s infinite; font-size: 11px;">${statusText}</span>`;
        }

        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td>
            <div class="account-meta">
              <div class="account-avatar">${initial}</div>
              <div>
                <strong style="color: #ffffff;">${acc.name || acc.screen_name}</strong>
                <div style="color: var(--text-muted); font-size: 12px;">@${acc.screen_name}</div>
              </div>
            </div>
          </td>
          <td>
            ${statusBadge}
          </td>
          <td>
            <strong style="color: #60a5fa; font-size: 15px;">${acc.post_count || 0}</strong>
          </td>
          <td>
            <strong style="color: #a78bfa; font-size: 15px;">${acc.interaction_count || 0}</strong>
          </td>
          <td>
            <div style="display: flex; gap: 8px;">
              ${isRunning ? `
                <button class="btn btn-stop" onclick="stopSingleAccount('${acc.screen_name}')">
                  ⏹️ Hentikan
                </button>
              ` : `
                <button class="btn btn-start" onclick="startSingleAccount('${acc.screen_name}')">
                  ▶️ Start Warming Up
                </button>
              `}
            </div>
          </td>
        `;
        tbody.appendChild(tr);
      });
    }

    // Render Giveaway Hunter Accounts Table (All accounts)
    function renderGiveawayTable(accounts, runningHunters, hunterStates) {
      const tbody = document.getElementById('giveaway-accounts-tbody');
      tbody.innerHTML = '';
      hunterStates = hunterStates || {};

      if (!accounts || accounts.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" style="text-align: center; color: var(--text-muted); padding: 24px;">Belum ada akun tersimpan.</td></tr>';
        return;
      }

      accounts.forEach(acc => {
        const uLower = acc.screen_name.toLowerCase();
        const isRunning = runningHunters.includes(uLower);
        const initial = acc.screen_name.charAt(0).toUpperCase();
        const st = hunterStates[uLower] || {};

        let statusBadge = '<span class="badge badge-primary">⚪ Standby</span>';
        if (isRunning) {
          const statusText = st.status || '🟢 Memindai...';
          statusBadge = `<span class="badge badge-warning" style="animation: pulse 1.5s infinite; font-size: 11px;">${statusText}</span>`;
        }

        const hasWallet = Boolean(acc.evm_address || acc.solana_address);
        let walletDisplay = '';
        if (acc.evm_address) {
          walletDisplay += `<div style="font-size: 11px; font-family: var(--mono); color: #93c5fd;">EVM: ${formatShortAddr(acc.evm_address)}</div>`;
        }
        if (acc.solana_address) {
          walletDisplay += `<div style="font-size: 11px; font-family: var(--mono); color: #c084fc;">SOL: ${formatShortAddr(acc.solana_address)}</div>`;
        }
        if (!hasWallet) {
          walletDisplay = '<span style="color: #f87171; font-size: 11.5px;">⚠️ Belum ada wallet</span>';
        }

        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td>
            <div class="account-meta">
              <div class="account-avatar">${initial}</div>
              <div>
                <strong style="color: #ffffff;">${acc.name || acc.screen_name}</strong>
                <div style="color: var(--text-muted); font-size: 12px;">@${acc.screen_name}</div>
              </div>
            </div>
          </td>
          <td>
            ${walletDisplay}
          </td>
          <td>
            ${statusBadge}
          </td>
          <td>
            <strong style="color: #c084fc; font-size: 15px;">${acc.airdrop_count || 0}</strong>
          </td>
          <td>
            <div style="display: flex; gap: 8px;">
              ${isRunning ? `
                <button class="btn btn-stop" onclick="stopSingleHunter('${acc.screen_name}')">
                  ⏹️ Hentikan
                </button>
              ` : `
                <button class="btn btn-hunter" onclick="startSingleHunter('${acc.screen_name}')" ${!hasWallet ? 'disabled title="Isi wallet terlebih dahulu di Submit Address"' : ''}>
                  ▶️ Start Scraping
                </button>
              `}
            </div>
          </td>
        `;
        tbody.appendChild(tr);
      });
    }

    // Render Live Activity Feed
    function renderActivityFeed(activities) {
      const feed = document.getElementById('activity-feed');
      feed.innerHTML = '';

      if (!activities || activities.length === 0) {
        feed.innerHTML = '<div style="color: var(--text-muted); text-align: center; padding: 20px;">Belum ada riwayat aktivitas warming up.</div>';
        return;
      }

      activities.slice(0, 25).forEach(act => {
        const isPost = act.action === 'post';
        const item = document.createElement('div');
        item.className = 'feed-item';
        item.innerHTML = `
          <div class="feed-header">
            <span style="font-weight: 700; color: ${isPost ? '#60a5fa' : '#a78bfa'};">
              ${isPost ? '📝 Yapping Post' : '💬 5x Like & Komentar'} · @${act.account}
            </span>
            <span style="color: var(--text-muted); font-size: 11px; font-family: var(--mono);">${act.timestamp}</span>
          </div>
          <div class="feed-content">${act.text}</div>
        `;
        feed.appendChild(item);
      });
    }

    // Render Wallet Editor Table Per-Akun
    function renderWalletEditorTable(accounts) {
      const tbody = document.getElementById('wallet-accounts-tbody');
      
      const existingEvmValues = {};
      const existingSolValues = {};
      accounts.forEach(acc => {
        const evmEl = document.getElementById('wallet-evm-' + acc.screen_name);
        const solEl = document.getElementById('wallet-sol-' + acc.screen_name);
        if (evmEl && document.activeElement === evmEl) {
          existingEvmValues[acc.screen_name] = evmEl.value;
        }
        if (solEl && document.activeElement === solEl) {
          existingSolValues[acc.screen_name] = solEl.value;
        }
      });

      tbody.innerHTML = '';

      if (!accounts || accounts.length === 0) {
        tbody.innerHTML = '<tr><td colspan="4" style="text-align: center; color: var(--text-muted); padding: 24px;">Belum ada akun.</td></tr>';
        return;
      }

      accounts.forEach(acc => {
        const initial = acc.screen_name.charAt(0).toUpperCase();

        const currentEvm = existingEvmValues[acc.screen_name] !== undefined 
          ? existingEvmValues[acc.screen_name] 
          : (acc.evm_address || '');

        const currentSol = existingSolValues[acc.screen_name] !== undefined 
          ? existingSolValues[acc.screen_name] 
          : (acc.solana_address || '');

        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td>
            <div class="account-meta">
              <div class="account-avatar">${initial}</div>
              <div>
                <strong style="color: #ffffff;">${acc.name || acc.screen_name}</strong>
                <div style="color: var(--text-muted); font-size: 12px;">@${acc.screen_name}</div>
              </div>
            </div>
          </td>
          <td>
            <input type="text" class="form-control mono" id="wallet-evm-${acc.screen_name}" 
                   value="${currentEvm}" placeholder="0x... (Alamat EVM 42 Karakter)">
          </td>
          <td>
            <input type="text" class="form-control mono" id="wallet-sol-${acc.screen_name}" 
                   value="${currentSol}" placeholder="Base58 (Alamat Solana 32-44 Karakter)">
          </td>
          <td style="text-align: center;">
            <button class="btn btn-outline" style="padding: 6px 12px; font-size: 12px;" onclick="saveSingleWallet('${acc.screen_name}')">
              💾 Simpan
            </button>
          </td>
        `;
        tbody.appendChild(tr);
      });
    }

    // Submit Tambah Akun
    async function submitAddAccount(e) {
      e.preventDefault();
      const authToken = document.getElementById('input-auth-token').value.trim();
      const ct0 = document.getElementById('input-ct0').value.trim();
      const screenName = document.getElementById('input-screen-name').value.trim();
      const displayName = document.getElementById('input-display-name').value.trim();

      const btn = document.getElementById('btn-submit-account');
      btn.disabled = true;
      btn.innerText = '⏳ Menyimpan...';

      try {
        const res = await fetch('/api/accounts/add', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            auth_token: authToken,
            ct0: ct0,
            screen_name: screenName,
            name: displayName
          })
        });

        const d = await res.json();
        showToast(d.message);

        if (d.success) {
          document.getElementById('form-add-account').reset();
          fetchOverview();
        }
      } catch (err) {
        showToast('Error: ' + err.message);
      } finally {
        btn.disabled = false;
        btn.innerText = '➕ Simpan & Tambahkan Akun';
      }
    }

    // Remove Account (Equal for all accounts)
    async function removeAccount(screenName) {
      if (confirm(`Apakah Anda yakin ingin menghapus akun @${screenName} dari sistem?`)) {
        showToast(`Menghapus @${screenName}...`);
        const res = await fetch('/api/accounts/remove', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ screen_name: screenName })
        });
        const d = await res.json();
        showToast(d.message);
        fetchOverview();
      }
    }

    // Start/Stop Single Yapping
    async function startSingleAccount(screenName) {
      showToast(`⚡ Memulai yapping berulang untuk @${screenName}... (Jeda 10-30m per siklus)`);
      const res = await fetch('/api/trigger-single', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ screen_name: screenName })
      });
      const d = await res.json();
      showToast(d.message);
      fetchOverview();
    }

    async function stopSingleAccount(screenName) {
      showToast(`⏹️ Menghentikan pemanasan @${screenName}...`);
      const res = await fetch('/api/stop-single', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ screen_name: screenName })
      });
      const d = await res.json();
      showToast(d.message);
      fetchOverview();
    }

    // Start/Stop All Yapping
    async function startAllYapping() {
      if (confirm('Mulai Yapping Random untuk SEMUA akun sekaligus?')) {
        for (const acc of GLOBAL_ACCOUNTS) {
          await fetch('/api/trigger-single', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ screen_name: acc.screen_name })
          });
        }
        showToast('🚀 Yapping Random telah dimulai untuk semua akun!');
        fetchOverview();
      }
    }

    async function stopAllYapping() {
      if (confirm('Hentikan Yapping Random untuk SEMUA akun?')) {
        for (const acc of GLOBAL_ACCOUNTS) {
          await fetch('/api/stop-single', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ screen_name: acc.screen_name })
          });
        }
        showToast('⏹️ Seluruh proses yapping dihentikan.');
        fetchOverview();
      }
    }

    // Start/Stop Single Giveaway Hunter
    async function startSingleHunter(screenName) {
      const cat = document.getElementById('select-category').value;
      const count = document.getElementById('select-count').value;

      showToast(`🚀 Memulai scraping giveaway @${screenName} [${cat}] (${count} target)...`);
      const res = await fetch('/api/airdrop-hunter/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ screen_name: screenName, category: cat, target_count: count })
      });
      const d = await res.json();
      showToast(d.message);
      fetchOverview();
    }

    async function stopSingleHunter(screenName) {
      showToast(`⏹️ Menghentikan scraping giveaway @${screenName}...`);
      const res = await fetch('/api/airdrop-hunter/stop', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ screen_name: screenName })
      });
      const d = await res.json();
      showToast(d.message);
      fetchOverview();
    }

    // Start/Stop All Giveaway Hunter
    async function startAllHunter() {
      const cat = document.getElementById('select-category').value;
      const count = document.getElementById('select-count').value;

      if (confirm(`Mulai Scraping Giveaway [${cat}] untuk SEMUA akun yang memiliki wallet?`)) {
        showToast('🚀 Memulai perburuan giveaway untuk semua akun...');
        const res = await fetch('/api/airdrop-hunter/start', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ screen_name: 'all', category: cat, target_count: count })
        });
        const d = await res.json();
        showToast(d.message);
        fetchOverview();
      }
    }

    async function stopAllHunter() {
      if (confirm('Hentikan Scraping Giveaway untuk SEMUA akun?')) {
        showToast('⏹️ Menghentikan seluruh proses scraping giveaway...');
        const res = await fetch('/api/airdrop-hunter/stop', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ screen_name: 'all' })
        });
        const d = await res.json();
        showToast(d.message);
        fetchOverview();
      }
    }

    // Save Single Wallet Address
    async function saveSingleWallet(screenName) {
      const evmInput = document.getElementById('wallet-evm-' + screenName);
      const solInput = document.getElementById('wallet-sol-' + screenName);

      const evm = evmInput ? evmInput.value.trim() : '';
      const sol = solInput ? solInput.value.trim() : '';

      showToast(`Menyimpan wallet untuk @${screenName}...`);
      try {
        const res = await fetch('/api/accounts/update-wallet', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            screen_name: screenName,
            evm_address: evm,
            solana_address: sol
          })
        });
        const d = await res.json();
        showToast(d.message);
        if (d.success) {
          fetchOverview();
        }
      } catch (err) {
        showToast('Error: ' + err.message);
      }
    }

    // Save All Wallets
    async function saveAllWallets() {
      const payload = {};
      GLOBAL_ACCOUNTS.forEach(acc => {
        const evmEl = document.getElementById('wallet-evm-' + acc.screen_name);
        const solEl = document.getElementById('wallet-sol-' + acc.screen_name);
        payload[acc.screen_name] = {
          evm_address: evmEl ? evmEl.value.trim() : '',
          solana_address: solEl ? solEl.value.trim() : ''
        };
      });

      showToast('Menyimpan semua alamat wallet...');
      try {
        const res = await fetch('/api/accounts/update-all-wallets', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ wallets: payload })
        });
        const d = await res.json();
        showToast(d.message);
        fetchOverview();
      } catch (err) {
        showToast('Error: ' + err.message);
      }
    }

    // Fetch Airdrop History
    async function fetchAirdropHistory() {
      try {
        const res = await fetch('/api/airdrop-history');
        const data = await res.json();

        const tbody = document.getElementById('airdrop-history-tbody');
        tbody.innerHTML = '';

        if (!data.items || data.items.length === 0) {
          tbody.innerHTML = '<tr><td colspan="7" style="text-align: center; color: var(--text-muted); padding: 30px;">Belum ada riwayat entri giveaway yang tercatat.</td></tr>';
          return;
        }

        data.items.forEach(item => {
          const tr = document.createElement('tr');
          const isEvm = item.wallet_type === 'EVM';
          const badgeType = isEvm 
            ? '<span class="badge badge-evm">EVM (0x)</span>' 
            : '<span class="badge badge-sol">SOLANA</span>';

          const actionsFormatted = (item.actions_done || []).map(a => 
            `<span style="font-size: 11px; background: rgba(255,255,255,0.06); padding: 2px 6px; border-radius: 4px; margin-right: 4px; display: inline-block;">${a}</span>`
          ).join('');

          tr.innerHTML = `
            <td style="font-size: 12px; color: var(--text-muted); font-family: var(--mono);">${item.timestamp}</td>
            <td><strong style="color: #34d399;">@${item.account || '-'}</strong></td>
            <td><strong style="color: #60a5fa;">@${item.author}</strong></td>
            <td>${badgeType}</td>
            <td style="font-size: 13px; max-width: 380px;">${item.text}</td>
            <td>${actionsFormatted}</td>
            <td>
              <a href="${item.url}" target="_blank" class="btn btn-outline" style="padding: 4px 8px; font-size: 11px;">Buka ↗</a>
            </td>
          `;
          tbody.appendChild(tr);
        });

      } catch (e) {
        console.error("Gagal memuat airdrop history:", e);
      }
    }

    // Auto-refresh interval (Setiap 3 detik)
    fetchOverview();
    setInterval(() => {
      fetchOverview();
      const giveawayTab = document.getElementById('tab-giveaway');
      if (giveawayTab && giveawayTab.classList.contains('active')) {
        fetchAirdropHistory();
      }
    }, 3000);
  </script>
</body>
</html>
"""


# ==============================================================================
# 🌐 API ROUTE HANDLERS
# ==============================================================================

async def handle_index(request):
    """Menampilkan halaman utama dashboard HTML."""
    return web.Response(text=HTML_TEMPLATE, content_type="text/html")


async def handle_api_overview(request):
    """Mengembalikan data lengkap status akun, riwayat, dan statistik."""
    data = load_accounts()
    active_name = data.get("active_account", "")
    all_accounts = data.get("accounts", {})

    warmup_hist = {}
    if WARMUP_HISTORY_FILE.exists():
        try:
            with open(WARMUP_HISTORY_FILE, "r", encoding="utf-8") as f:
                warmup_hist = json.load(f)
        except Exception:
            pass

    airdrop_hist = {}
    if AIRDROP_HISTORY_FILE.exists():
        try:
            with open(AIRDROP_HISTORY_FILE, "r", encoding="utf-8") as f:
                airdrop_hist = json.load(f)
        except Exception:
            pass

    # Hitung giveaway yang diikuti per-akun
    airdrop_per_account = {}
    for entry in airdrop_hist.values():
        acc = entry.get("account", "").strip().lstrip("@").lower()
        if acc:
            airdrop_per_account[acc] = airdrop_per_account.get(acc, 0) + 1

    accounts_list = []
    total_posts = 0
    total_interactions = 0
    recent_activities = []

    for key, acc in all_accounts.items():
        uname = acc.get("screen_name", key)
        is_cli_active = (key.lower() == active_name.lower() or uname.lower() == active_name.lower())

        events = warmup_hist.get(uname, [])
        p_count = sum(1 for e in events if e.get("action") == "post")
        i_count = sum(1 for e in events if e.get("action") == "interaction")

        total_posts += p_count
        total_interactions += i_count

        last_post_text = ""
        last_active = "-"
        if events:
            last_ev = events[-1]
            last_active = last_ev.get("timestamp", "-")
            for e in reversed(events):
                if e.get("action") == "post":
                    last_post_text = e.get("details", {}).get("text", "")
                    break

        for e in events:
            action_type = e.get("action", "")
            txt = ""
            if action_type == "post":
                txt = f'"{e.get("details", {}).get("text", "")}"'
            else:
                det = e.get("details", {})
                if isinstance(det, dict) and "items" in det:
                    txt = "; ".join(det["items"][:2])
                elif isinstance(det, dict) and "details" in det:
                    txt = str(det["details"])
                else:
                    txt = str(det)

            recent_activities.append({
                "account": uname,
                "action": action_type,
                "timestamp": e.get("timestamp", "-"),
                "text": txt
            })

        accounts_list.append({
            "screen_name": uname,
            "name": acc.get("name", uname),
            "added_at": acc.get("added_at", "-"),
            "auth_token": acc.get("auth_token", ""),
            "ct0": acc.get("ct0", ""),
            "evm_address": acc.get("evm_address", ""),
            "solana_address": acc.get("solana_address", ""),
            "post_count": p_count,
            "interaction_count": i_count,
            "airdrop_count": airdrop_per_account.get(uname.lower(), 0),
            "last_post_text": last_post_text,
            "last_active": last_active
        })

    recent_activities.sort(key=lambda x: x["timestamp"], reverse=True)

    overview = {
        "total_accounts": len(all_accounts),
        "total_yapping_posts": total_posts,
        "total_interactions": total_interactions,
        "total_airdrop_entered": len(airdrop_hist),
        "accounts": accounts_list,
        "recent_activities": recent_activities[:35],
        "running_warm": list(RUNNING_WARM_TASKS.keys()),
        "warm_states": WARM_ACCOUNTS_STATE,
        "running_hunter": list(RUNNING_HUNTER_TASKS.keys()),
        "hunter_states": HUNTER_ACCOUNTS_STATE
    }

    return web.json_response(overview)


async def handle_api_add_account(request):
    """Menambahkan akun Twitter baru menggunakan auth_token dan ct0."""
    try:
        data = await request.json()
        auth_token = data.get("auth_token", "").strip().replace('"', '').replace("'", "")
        ct0 = data.get("ct0", "").strip().replace('"', '').replace("'", "")
        screen_name = data.get("screen_name", "").strip().lstrip("@")
        name = data.get("name", "").strip()

        if not auth_token or not ct0:
            return web.json_response({
                "success": False, 
                "message": "auth_token dan ct0 wajib diisi!"
            })

        if not screen_name:
            try:
                ok, detected_user, detected_name = await verify_tokens_with_browser(auth_token, ct0)
                if ok and detected_user:
                    screen_name = detected_user
                    if not name and detected_name:
                        name = detected_name
                else:
                    return web.json_response({
                        "success": False, 
                        "message": f"Gagal mendeteksi akun otomatis: {detected_user}. Harap isi Username secara manual."
                    })
            except Exception as e:
                return web.json_response({
                    "success": False, 
                    "message": f"Gagal mendeteksi akun via browser: {e}. Harap isi Username secara manual."
                })

        if not name:
            name = screen_name

        add_account(
            screen_name=screen_name,
            name=name,
            auth_token=auth_token,
            ct0=ct0,
            set_as_active=False
        )

        return web.json_response({
            "success": True, 
            "message": f"✓ Akun @{screen_name} ({name}) berhasil ditambahkan!"
        })
    except Exception as e:
        return web.json_response({"success": False, "message": str(e)})


async def handle_api_remove_account(request):
    """Menghapus akun Twitter dari sistem (berlaku untuk semua akun)."""
    try:
        data = await request.json()
        screen_name = data.get("screen_name", "").strip().lstrip("@")
        if not screen_name:
            return web.json_response({"success": False, "message": "Username wajib diisi"})

        ok = remove_account(screen_name)
        if ok:
            return web.json_response({"success": True, "message": f"✓ Akun @{screen_name} berhasil dihapus!"})
        else:
            return web.json_response({"success": False, "message": f"Akun @{screen_name} tidak ditemukan."})
    except Exception as e:
        return web.json_response({"success": False, "message": str(e)})


async def handle_api_update_wallet(request):
    """Menyimpan alamat wallet EVM dan Solana untuk satu akun tertentu."""
    try:
        data = await request.json()
        target = data.get("screen_name", "").strip().lstrip("@").lower()
        evm = data.get("evm_address", "").strip()
        sol = data.get("solana_address", "").strip()

        if evm and not is_valid_evm_address(evm):
            return web.json_response({
                "success": False, 
                "message": "Format alamat EVM tidak valid! Harus diawali 0x dan 40 karakter heksadesimal."
            })

        if sol and not is_valid_solana_address(sol):
            return web.json_response({
                "success": False, 
                "message": "Format alamat Solana tidak valid! Harus berupa Base58 (32-44 karakter)."
            })

        accs_data = load_accounts()
        accounts = accs_data.get("accounts", {})

        matched_key = None
        for k, v in accounts.items():
            if k.lower() == target or v.get("screen_name", "").lower() == target:
                matched_key = k
                break

        if not matched_key:
            return web.json_response({"success": False, "message": f"Akun @{target} tidak ditemukan"})

        accounts[matched_key]["evm_address"] = evm
        accounts[matched_key]["solana_address"] = sol
        save_accounts(accs_data)

        # Sinkronkan ke wallets.json jika akun sedang aktif di CLI
        if matched_key.lower() == accs_data.get("active_account", "").lower():
            g_cfg = load_wallet_config()
            g_cfg["evm_address"] = evm
            g_cfg["solana_address"] = sol
            save_wallet_config(g_cfg)

        return web.json_response({
            "success": True, 
            "message": f"✓ Alamat wallet untuk @{target} berhasil disimpan!"
        })
    except Exception as e:
        return web.json_response({"success": False, "message": str(e)})


async def handle_api_update_all_wallets(request):
    """Menyimpan alamat wallet untuk semua akun sekaligus."""
    try:
        data = await request.json()
        wallets_map = data.get("wallets", {})

        accs_data = load_accounts()
        accounts = accs_data.get("accounts", {})

        updated_count = 0
        for uname, w in wallets_map.items():
            clean_u = uname.strip().lstrip("@").lower()
            evm = w.get("evm_address", "").strip()
            sol = w.get("solana_address", "").strip()

            if evm and not is_valid_evm_address(evm):
                continue
            if sol and not is_valid_solana_address(sol):
                continue

            for k, v in accounts.items():
                if k.lower() == clean_u or v.get("screen_name", "").lower() == clean_u:
                    accounts[k]["evm_address"] = evm
                    accounts[k]["solana_address"] = sol
                    updated_count += 1
                    break

        save_accounts(accs_data)

        active_u = accs_data.get("active_account", "").lower()
        if active_u in accounts:
            g_cfg = load_wallet_config()
            g_cfg["evm_address"] = accounts[active_u].get("evm_address", "")
            g_cfg["solana_address"] = accounts[active_u].get("solana_address", "")
            save_wallet_config(g_cfg)

        return web.json_response({
            "success": True, 
            "message": f"✓ Berhasil memperbarui alamat wallet untuk {updated_count} akun!"
        })
    except Exception as e:
        return web.json_response({"success": False, "message": str(e)})


async def handle_api_switch_account(request):
    """Menangani pergantian akun aktif untuk CLI."""
    try:
        data = await request.json()
        target = data.get("screen_name", "").strip()
        if not target:
            return web.json_response({"success": False, "error": "Username tidak boleh kosong"})

        ok = switch_account(target)
        if ok:
            acc_data = load_accounts().get("accounts", {}).get(target.lower(), {})
            if acc_data.get("evm_address") or acc_data.get("solana_address"):
                g_cfg = load_wallet_config()
                if acc_data.get("evm_address"):
                    g_cfg["evm_address"] = acc_data["evm_address"]
                if acc_data.get("solana_address"):
                    g_cfg["solana_address"] = acc_data["solana_address"]
                save_wallet_config(g_cfg)

            return web.json_response({"success": True, "active_account": target})
        else:
            return web.json_response({"success": False, "error": "Gagal beralih akun"})
    except Exception as e:
        return web.json_response({"success": False, "error": str(e)})


# ==============================================================================
# 💬 YAPPING RANDOM LOOPING HANDLERS
# ==============================================================================

async def run_single_warm_loop(acc_data: dict):
    """Looping otomatis pemanasan untuk akun: Post + 5x Like & Comment + Jeda 10-30 Menit."""
    target = acc_data.get("screen_name", "")
    target_key = target.lower()
    from account_warmer import warm_up_single_account, get_used_yapping_posts

    cycle = 1
    try:
        while True:
            WARM_ACCOUNTS_STATE[target_key] = {
                "cycle": cycle,
                "status": f"⚡ Siklus #{cycle}: Post & Interaksi 5x...",
                "next_run_ts": 0
            }
            print(f"\n{CYAN}▶️ [YAPPING LOOP] Memulai Siklus #{cycle} untuk @{target}...{RESET}")
            try:
                used = get_used_yapping_posts()
                await warm_up_single_account(
                    account_info=acc_data,
                    used_yappings=used,
                    do_post=True,
                    do_interaction=True,
                    comments_per_cycle=5,
                    force_post=True,
                    headless=True,
                    dry_run=False
                )
                print(f"{GREEN}✓ Siklus #{cycle} Yapping @{target} selesai!{RESET}")
            except asyncio.CancelledError:
                raise
            except Exception as err:
                logger.error(f"Error pada siklus #{cycle} akun @{target}: {err}")
                print(f"{RED}⚠️ Kendala siklus #{cycle} akun @{target}: {err}{RESET}")

            # Jeda antar siklus: 10 - 30 menit
            delay_sec = random.randint(10 * 60, 30 * 60)
            next_ts = datetime.now().timestamp() + delay_sec
            WARM_ACCOUNTS_STATE[target_key]["next_run_ts"] = next_ts

            print(f"   ⏱️ Jeda antar siklus untuk @{target}: {delay_sec // 60}m {delay_sec % 60}s...")

            while True:
                now_ts = datetime.now().timestamp()
                remaining = int(next_ts - now_ts)
                if remaining <= 0:
                    break
                rem_m = remaining // 60
                rem_s = remaining % 60
                WARM_ACCOUNTS_STATE[target_key]["status"] = f"⏳ Jeda #{cycle+1} ({rem_m}m {rem_s:02d}s)"
                await asyncio.sleep(min(3, remaining))

            cycle += 1

    except asyncio.CancelledError:
        print(f"   ⏹️ Pemanasan berulang @{target} dihentikan.")
    finally:
        RUNNING_WARM_TASKS.pop(target_key, None)
        WARM_ACCOUNTS_STATE.pop(target_key, None)


async def handle_api_trigger_single(request):
    """Memicu pemanasan berulang untuk akun tertentu."""
    try:
        data = await request.json()
        target = data.get("screen_name", "").strip().lstrip("@")
        if not target:
            return web.json_response({"success": False, "message": "Username tidak valid"})

        all_accs = load_accounts().get("accounts", {})
        acc_data = None
        for k, v in all_accs.items():
            if k.lower() == target.lower() or v.get("screen_name", "").lower() == target.lower():
                acc_data = v
                target = v.get("screen_name", k)
                break

        if not acc_data:
            return web.json_response({"success": False, "message": f"Akun @{target} tidak ditemukan"})

        target_key = target.lower()
        if target_key in RUNNING_WARM_TASKS and not RUNNING_WARM_TASKS[target_key].done():
            return web.json_response({"success": False, "message": f"Akun @{target} sudah aktif yapping!"})

        task = asyncio.create_task(run_single_warm_loop(acc_data))
        RUNNING_WARM_TASKS[target_key] = task
        WARM_ACCOUNTS_STATE[target_key] = {
            "cycle": 1,
            "status": "Memulai Siklus #1...",
            "next_run_ts": 0
        }

        return web.json_response({
            "success": True, 
            "message": f"⚡ Yapping Random looping untuk @{target} dimulai! (Jeda 10-30m per siklus)"
        })
    except Exception as e:
        return web.json_response({"success": False, "message": str(e)})


async def handle_api_stop_single(request):
    """Menghentikan pemanasan looping untuk akun tertentu."""
    try:
        data = await request.json()
        target = data.get("screen_name", "").strip().lstrip("@")
        target_key = target.lower()
        task = RUNNING_WARM_TASKS.get(target_key)
        if task and not task.done():
            task.cancel()
            RUNNING_WARM_TASKS.pop(target_key, None)
            WARM_ACCOUNTS_STATE.pop(target_key, None)
            return web.json_response({"success": True, "message": f"⏹️ Yapping @{target} berhasil dihentikan!"})
        else:
            RUNNING_WARM_TASKS.pop(target_key, None)
            WARM_ACCOUNTS_STATE.pop(target_key, None)
            return web.json_response({"success": True, "message": f"Akun @{target} tidak sedang berjalan."})
    except Exception as e:
        return web.json_response({"success": False, "message": str(e)})


# ==============================================================================
# 🎁 SCRAPING GIVEAWAY LOOPING HANDLERS (BERLAKU UNTUK SEMUA AKUN)
# ==============================================================================

async def run_single_hunter_loop(acc_data: dict, cat: str, count: int):
    """Looping scraping giveaway untuk akun: Pindai & Drop Wallet + Jeda 10-30 Menit."""
    target = acc_data.get("screen_name", "")
    target_key = target.lower()
    from browser_hunter import run_hunter

    cycle = 1
    try:
        while True:
            HUNTER_ACCOUNTS_STATE[target_key] = {
                "is_running": True,
                "category": cat,
                "target_count": count,
                "cycle": cycle,
                "status": f"⚡ Siklus #{cycle}: Memindai [{cat}] ({count} target)...",
                "next_run_ts": 0
            }
            print(f"\n{MAGENTA}🚀 [GIVEAWAY LOOP @{target}] Memulai Siklus #{cycle} [{cat}] ({count} target)...{RESET}")
            try:
                await run_hunter(
                    category=cat,
                    target_count=count,
                    max_age_hours=12.0,
                    headless=True,
                    account_info=acc_data
                )
                print(f"{GREEN}✓ Siklus #{cycle} Scraping Giveaway @{target} selesai!{RESET}")
            except asyncio.CancelledError:
                raise
            except Exception as err:
                logger.error(f"Error pada siklus #{cycle} hunter @{target}: {err}")
                print(f"{RED}⚠️ Kendala siklus #{cycle} hunter @{target}: {err}{RESET}")

            # Jeda antar siklus: 10 - 30 menit
            delay_sec = random.randint(10 * 60, 30 * 60)
            next_ts = datetime.now().timestamp() + delay_sec
            HUNTER_ACCOUNTS_STATE[target_key]["next_run_ts"] = next_ts

            print(f"   ⏱️ Jeda antar siklus giveaway untuk @{target}: {delay_sec // 60}m {delay_sec % 60}s...")

            while True:
                now_ts = datetime.now().timestamp()
                remaining = int(next_ts - now_ts)
                if remaining <= 0:
                    break
                rem_m = remaining // 60
                rem_s = remaining % 60
                HUNTER_ACCOUNTS_STATE[target_key]["status"] = f"⏳ Jeda #{cycle+1} ({rem_m}m {rem_s:02d}s)"
                await asyncio.sleep(min(3, remaining))

            cycle += 1

    except asyncio.CancelledError:
        print(f"   ⏹️ Scraping giveaway @{target} dihentikan.")
    finally:
        RUNNING_HUNTER_TASKS.pop(target_key, None)
        HUNTER_ACCOUNTS_STATE.pop(target_key, None)


async def handle_api_start_airdrop_hunter(request):
    """Memicu scraping giveaway looping untuk akun tertentu atau semua akun."""
    try:
        data = await request.json()
        target = data.get("screen_name", "").strip().lstrip("@")
        cat = data.get("category", "ALL").upper()
        count = int(data.get("target_count", 10))

        all_accs = load_accounts().get("accounts", {})

        # Jalankan semua akun
        if target.lower() == "all":
            started = []
            for k, acc in all_accs.items():
                ukey = k.lower()
                if ukey in RUNNING_HUNTER_TASKS and not RUNNING_HUNTER_TASKS[ukey].done():
                    continue
                if not acc.get("evm_address") and not acc.get("solana_address"):
                    continue
                task = asyncio.create_task(run_single_hunter_loop(acc, cat, count))
                RUNNING_HUNTER_TASKS[ukey] = task
                started.append(acc.get("screen_name", k))
                await asyncio.sleep(2)

            if not started:
                return web.json_response({
                    "success": False, 
                    "message": "Tidak ada akun dengan alamat wallet yang siap dijalankan! Isi wallet terlebih dahulu."
                })
            return web.json_response({
                "success": True, 
                "message": f"🚀 Scraping giveaway dimulai untuk {len(started)} akun: {', '.join('@' + u for u in started)}!"
            })

        # Jalankan satu akun
        acc_data = None
        for k, v in all_accs.items():
            if k.lower() == target.lower() or v.get("screen_name", "").lower() == target.lower():
                acc_data = v
                target = v.get("screen_name", k)
                break

        if not acc_data:
            return web.json_response({"success": False, "message": f"Akun @{target} tidak ditemukan"})

        if not acc_data.get("evm_address") and not acc_data.get("solana_address"):
            return web.json_response({
                "success": False, 
                "message": f"Akun @{target} belum memiliki alamat wallet EVM / Solana! Isi di menu Submit Address terlebih dahulu."
            })

        target_key = target.lower()
        if target_key in RUNNING_HUNTER_TASKS and not RUNNING_HUNTER_TASKS[target_key].done():
            return web.json_response({"success": False, "message": f"Akun @{target} sudah aktif scraping giveaway!"})

        task = asyncio.create_task(run_single_hunter_loop(acc_data, cat, count))
        RUNNING_HUNTER_TASKS[target_key] = task

        return web.json_response({
            "success": True, 
            "message": f"🚀 Scraping Giveaway untuk @{target} dimulai! (Looping jeda 10-30m per siklus)"
        })
    except Exception as e:
        return web.json_response({"success": False, "message": str(e)})


async def handle_api_stop_airdrop_hunter(request):
    """Menghentikan scraping giveaway untuk akun tertentu atau semua akun."""
    try:
        data = await request.json()
        target = data.get("screen_name", "").strip().lstrip("@")

        if target.lower() == "all" or not target:
            stopped = 0
            for k, task in list(RUNNING_HUNTER_TASKS.items()):
                if not task.done():
                    task.cancel()
                    stopped += 1
            RUNNING_HUNTER_TASKS.clear()
            HUNTER_ACCOUNTS_STATE.clear()
            return web.json_response({"success": True, "message": f"⏹️ Seluruh ({stopped}) scraper giveaway berhasil dihentikan."})

        target_key = target.lower()
        task = RUNNING_HUNTER_TASKS.get(target_key)
        if task and not task.done():
            task.cancel()
            RUNNING_HUNTER_TASKS.pop(target_key, None)
            HUNTER_ACCOUNTS_STATE.pop(target_key, None)
            return web.json_response({"success": True, "message": f"⏹️ Scraping giveaway @{target} berhasil dihentikan!"})
        else:
            RUNNING_HUNTER_TASKS.pop(target_key, None)
            HUNTER_ACCOUNTS_STATE.pop(target_key, None)
            return web.json_response({"success": True, "message": f"Akun @{target} tidak sedang berjalan."})
    except Exception as e:
        return web.json_response({"success": False, "message": str(e)})


async def handle_api_get_airdrop_history(request):
    """Mengambil riwayat entri giveaway terbaru."""
    items = []
    if AIRDROP_HISTORY_FILE.exists():
        try:
            with open(AIRDROP_HISTORY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                for tid, entry in data.items():
                    items.append({
                        "tweet_id": entry.get("tweet_id", tid),
                        "timestamp": entry.get("timestamp", "-"),
                        "account": entry.get("account", "-"),
                        "author": entry.get("author", "user"),
                        "text": entry.get("text", "")[:120],
                        "url": entry.get("url", f"https://x.com/i/status/{tid}"),
                        "wallet_type": entry.get("wallet_type", "EVM"),
                        "actions_done": entry.get("actions_done", [])
                    })
        except Exception:
            pass

    items.sort(key=lambda x: x["timestamp"], reverse=True)
    return web.json_response({"total": len(items), "items": items[:50]})


# ==============================================================================
# 🚀 SERVER ENTRYPOINT
# ==============================================================================

def create_app():
    app = web.Application()
    app.router.add_get("/", handle_index)
    app.router.add_get("/api/overview", handle_api_overview)
    app.router.add_post("/api/accounts/add", handle_api_add_account)
    app.router.add_post("/api/accounts/remove", handle_api_remove_account)
    app.router.add_post("/api/accounts/update-wallet", handle_api_update_wallet)
    app.router.add_post("/api/accounts/update-all-wallets", handle_api_update_all_wallets)
    app.router.add_post("/api/switch-account", handle_api_switch_account)

    # Yapping routes
    app.router.add_post("/api/trigger-single", handle_api_trigger_single)
    app.router.add_post("/api/stop-single", handle_api_stop_single)

    # Giveaway Hunter routes
    app.router.add_post("/api/airdrop-hunter/start", handle_api_start_airdrop_hunter)
    app.router.add_post("/api/airdrop-hunter/stop", handle_api_stop_airdrop_hunter)
    app.router.add_get("/api/airdrop-history", handle_api_get_airdrop_history)

    return app


def start_dashboard(host="127.0.0.1", port=5050):
    print(f"""{CYAN}{BOLD}
╔═══════════════════════════════════════════════════════════════╗
║         X / TWITTER MULTI-ACCOUNT WEB DASHBOARD               ║
║      Unified Suite · Semua Fitur untuk Semua Akun             ║
╚═══════════════════════════════════════════════════════════════╝{RESET}""")
    print(f"  🌐 Dashboard aktif di : {GREEN}{BOLD}http://{host}:{port}{RESET}")
    print(f"  📱 Akses via browser  : {CYAN}Buka http://localhost:{port} di Google Chrome{RESET}\n")

    app = create_app()
    web.run_app(app, host=host, port=port, print=None)


if __name__ == "__main__":
    start_dashboard()
