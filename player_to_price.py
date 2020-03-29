import numpy as np
import math
import time
import requests
import pandas as pd
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver import Firefox
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.keys import Keys

PATH = '/home/wooders/geckodriver'

BATTING_COLUMNS = ["name", "position", "year", "age", "team", "league", "games",
    "plate_appearances", "at_bats", "runs", "hits", "doubles", "triples", "home_runs",
    "runs_batted_in", "stolen_bases", "caught_stealing", "walks", "strike_outs",
    "batting_average", "on_base_percentage", "slugging_percentage", "on_base_plus_slugging",
    "on_base_plus_slugging_plus", "total_bases", "double_plays_grounded_into", "hit_by_pitch",
    "sacrafice_bunts", "sacrafice_flies", "intentional_walks", "position_2", "awards"]

PITCHING_COLUMNS = ["name", "year", "age", "team", "league", "wins", "loses",
    "win_loss_percentage", "earned_run_average", "games", "games_started",
    "games_finished", "complete_games", "shutouts", "saves", "innings_pitched",
    "hits_allowed", "runs_allowed", "earned_runs_allowed", "home_runs_allowed", "walks",
    "intentional_walks", "strike_outs", "hit_by_pitch", "balks", "wild_pitches",
    "batters_faced", "adjusted_earned_run_average", "fielding_independent_pitching",
    "walk_plus_hits_per_inning_pitched", "hits_per_nine_innings", "home_runs_per_nine_innings",
    "walks_per_nine_innings", "strike_outs_per_nine_innings", "strike_outs_per_walk", "awards"]


def get_names(filename, columns):
    '''
    Obtains players from csv who have played at least one season between
    1995-2010
    Inputs:
      - filename (csv): Either batting or pitching csv containing player data
      - columns (list): List of column headers
    Returns:
      - names (list): List containing player names active between
        1995-2010
    '''
    df = pd.read_csv(filename, names = columns, header = None)
    df = df.drop(df.index[0])
    df["year"] = pd.to_numeric(df["year"], errors='coerce')
    if df.columns[1] == "position":
        dfc = df.groupby(["name", "position"])['year']
    else:
        dfc = df.groupby("name")['year']
    df['first_year'] = dfc.transform('min')
    df['last_year'] = dfc.transform('max')

    df = df.loc[(df['first_year'] <= 2010) & (df['last_year'] >= 1995)]
    names = df["name"].unique()

    return names


def get_price_links(name):
    '''
    Takes a player name and obtains a list of links containing prices of
    cards associated with that player
    Inputs:
      - name (string): Player name to search prices for
    Returns:
      - price_links (list): List of links containing prices of card of given
        player
    '''
    search_base = 'https://www.psacard.com/auctionprices/#0|'
    price_links = []
    options = Options()
    options.headless = True
    browser = webdriver.Firefox(options = options, executable_path = PATH)
    page = search_base + name
    browser.get(page)
    soup = BeautifulSoup(browser.page_source, "html5lib")
    browser.quit()
    name = name.lower().replace(" ", "-")
    base = 'https://www.psacard.com'
    for link in soup.find_all('a', href = True):
        if '/auctionprices/baseball-cards' in link['href']:
            if name in link["href"]:
                price_links.append(base + link['href'])
            else:
                break
    price_links = list(set(price_links))

    return price_links


def price_info(soup, name):
    '''
    Takes the soup object from a link containing the price of the card of the
    associated player and returns a dictionary of the relevant data of the
    transactions of a card
    Inputs:
      - soup (BeautifulSoup object): Soup object of the link containing card
        data
      - name (string): Name of the player associated with the soup object
    Returns:
      - price_info (dictionary): Contains the relevant data on the transactions
        of a card
    '''
    image_data = [n for n in soup.find_all("div", {'class': 'item-image'})]
    images = []
    for n in image_data:
        html = str(n)
        if "href" not in html:
            images.append(math.nan)
            continue
        images.append(html.split('href="')[1].split('"')[0])
    # Get sale prices, Get dates of the sales, Get PSA grades and qualifiers, Get lot url links
    prices = [float(n.string.strip("$").replace(
        ",", "")) for n in soup.find_all("div", {'class': 'item item-price'})]
    dates = [n.string for n in soup.find_all("div",
        {'class': 'item item-date'})]
    grade_data = soup.find_all("div", {'class': 'item item-grade'})
    grades = []
    quals = []
    for n in grade_data:
        html = str(n)
        grades.append(html.split("</span>")[1].split("<")[0].strip())
        if "<strong>" in html:
            quals.append(html.split("<strong>")[1].split("<")[0].strip())
        else:
            quals.append(math.nan)
    lot_data = soup.find_all("div", {'class': 'item item-lot'})
    base_url = "https://www.psacard.com"
    lots = []
    for n in lot_data:
        html = str(n)
        if "href" not in html:
            lots.append(math.nan)
            continue
        lots.append(base_url + html.split('href="')[1].split('"')[0])
    # Get auction houses, Get names of the sellers, Get sale types (auction, BIN, Best Offer, etc)
    a_houses = [n.string for n in soup.find_all("div",
        {'class': 'item item-auctionhouse'})]
    sellers = [n.string for n in soup.find_all("div",
        {'class': 'item item-auctionname'})]
    sale_types = [n.string for n in soup.find_all("div",
        {'class': 'item item-auctiontype'})]
    # Get PSA certification numbers
    certs = [str(n).split("</span>")[1].split("<")[0] for n in soup.find_all(
        "div", {'class': 'item item-cert'})]
    names = [name] * len(dates)
    price_info = {
            "names": names,
            "date": dates,
            "grade": grades,
            "qualifier": quals,
            "price": prices,
            "auction_house": a_houses,
            "seller": sellers,
            "sale_type": sale_types,
            "psa_certification": certs,
            "img_url": images,
            "lot_url": lots}

    return price_info


def get_prices(names):
    '''
    Takes a dataframe of names to look for cards and their all transactions
    of that card type. Returns a dataframe of all transaction data of cards
    associated with the players in the names dataframe
    Inputs:
      - names_df (dataframe): Dataframe of names of players who played at least
        one season between 1995-2010
    Outputs:
      - df (dataframe): Dataframe containing all transactions of players in the
        names dataframe
    '''
    df_list = []
    for name in names:
        price_links = get_price_links(name)
        for link in price_links:
            page = requests.get(link)
            soup = BeautifulSoup(page.text, "html5lib")
            prices = price_info(soup, name)
            df = pd.DataFrame(prices)
            if df.empty:
                page = requests.get(link)
                soup = BeautifulSoup(page.text, "html5lib")
                time.sleep(5)
                prices = price_info(soup, name)
                df = pd.DataFrame(prices)
            df_list.append(df)
    df = pd.concat(df_list, axis = 0)

    return df


def aggregator(stats_filename, price_filename):
    '''
    Merge statistics file and the pricing of the cards file
    '''
    df_stats = pd.read_csv(stats_filename, header = None)
    df_stats = df_stats.drop(df_stats.index[0])
    df_price = pd.read_csv(price_filename)
    df_price = df_price.rename(columns = {"names": "name"})

    df_stats["year"] = pd.to_numeric(df_stats["year"], errors='coerce')
    dfc = df_stats.groupby(["name"])['year']
    df_stats['first_year'] = dfc.transform('min')
    df_stats['last_year'] = dfc.transform('max')
    df_stats = df_stats.loc[(df_stats['first_year'] <= 2010) & (df_stats['last_year'] >= 1995)]

    df_price["year_release"] = df_price.apply(lambda x: x["lot_url"][53:57], axis = 1)
    df_price["year_release"] = pd.to_numeric(df_price["year_release"], errors='coerce')
    df_price = df_price.loc[df_price["year_release"] >= min(df_stats["first_year"])]

    df_agg = pd.merge(df_stats, df_price, on=['name'], how='inner')
    df_agg = df_agg.loc[(df_agg["first_year"] <= df_agg["year_release"])]
    df_agg.dropna(subset = ["price"], inplace = True)

    return df_agg


if __name__ == '__main__':

    names_batting = get_names("batting_stats-2.csv", BATTING_COLUMNS)
    names_pitching = get_names("pitching_stats-2.csv", PITCHING_COLUMNS)
    get_prices(names_batting).to_csv("batting_cards.csv")
    get_prices(names_pitching).to_csv("pitching_cards.csv")
    aggregator("batting_stats-2.csv", "batting_cards.csv").to_csv("batting_all.csv")
    aggregator("pitching_stats-2.csv", "pitching_cards.csv").to_csv("pitching_all.csv")
