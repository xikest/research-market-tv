from bs4 import BeautifulSoup
import requests
import time
import pandas as pd
from tqdm import tqdm
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from market_research.tools import FileManager
from market_research.scraper._scaper_scheme import Scraper

class ModelScraper_s(Scraper):
    def __init__(self, enable_headless=True,
                 export_prefix="sony_model_info_web", intput_folder_path="input",  output_folder_path="results",
                 verbose: bool = False, wait_time=1):

        super().__init__(enable_headless=enable_headless, export_prefix=export_prefix,  intput_folder_path=intput_folder_path, output_folder_path=output_folder_path)

        self.tracking_log = verbose
        self.wait_time = wait_time
        self.file_manager = FileManager
        self.log_dir = "logs/sony/models"
        if self.tracking_log:
            FileManager.delete_dir(self.log_dir)
            FileManager.make_dir(self.log_dir)

    def get_models_info(self, format_df:bool=True, temporary_year_marking=False, show_visit:bool=False):
        print("collecting models")
        url_series_set = self._get_url_series()
        url_series_dict = {}
        for url in url_series_set:
            url_models = self._get_models(url=url)
            url_series_dict.update(url_models)
        print("number of total model:", len(url_series_dict))
        print("collecting spec")
        visit_url_dict = {}
        dict_models = {}
        cnt_loop=2
        for cnt in range(cnt_loop):#main try
            for key, url_model in tqdm(url_series_dict.items()):
                try:
                    dict_models[key] = self._get_global_spec(url=url_model)
                    visit_url_dict[key] = url_model
                except Exception as e:
                    if cnt == cnt_loop - 1:
                        print(f"\nFailed to get info from {key}")
                        print(e)
                    pass
            break
        if show_visit:
            print("\n")
            for model, url in visit_url_dict.items():  print(f"{model}: {url}")

        if format_df:
            df_models = pd.DataFrame.from_dict(dict_models).T
            if temporary_year_marking:
                df_models['year'] = df_models['year'].fillna("2024") ## 임시
            FileManager.df_to_excel(df_models.reset_index(), file_name=self.output_xlsx_name, sheet_name="raw_na", mode='w')
            return df_models
        else:
            return dict_models


    def _get_url_series(self) -> set:
        """
        Get the series URLs by scrolling down the main page.
        """
        url = "https://electronics.sony.com/tv-video/televisions/c/all-tvs/"
        prefix = "https://electronics.sony.com/"
        step = 200
        url_series = set()
        try_total = 5
        for _ in range(2): #page_checker
            for cnt_try in range(try_total):
                driver = self.web_driver.get_chrome()
                try:
                    driver.get(url=url)
                    time.sleep(self.wait_time)
                    scroll_distance_total = self.web_driver.get_scroll_distance_total()
                    scroll_distance = 0
                    while scroll_distance < scroll_distance_total:
                        for _ in range(2):
                            html = driver.page_source
                            soup = BeautifulSoup(html, 'html.parser')
                            elements = soup.find_all('a', class_="custom-product-grid-item__product-name")
                            for element in elements:
                                url_series.add(prefix + element['href'].strip())
                            driver.execute_script(f"window.scrollBy(0, {step});")
                            time.sleep(self.wait_time)
                            scroll_distance += step
                    break
                except Exception as e:
                    if self.tracking_log:
                        if cnt_try + 1 == try_total:
                            print(f"collecting primary url error from {url}")
                finally:
                    driver.quit()
        print("The website scan has been completed.")
        print(f"number of total series: {len(url_series)}")
        if self.tracking_log:
            print(url_series)
        return url_series

    def _get_models(self, url: str) -> dict:
        """
        Extract all model URLs from a given series URL.
        """
        try_total = 5
        dict_url_models = {}
        for cnt_try in range(try_total):
            driver = self.web_driver.get_chrome()
            driver.get(url=url)
            time.sleep(self.wait_time)
            try:
                try:
                    elements = driver.find_element(By.XPATH,
                                                      '//*[@id="PDPOveriewLink"]/div[1]/div[2]/div[1]/div[2]/div/app-custom-product-summary/div[2]/div/div[1]/app-custom-product-variants/div/app-custom-variant-selector/div/div[2]')
                except Exception:
                    elements = driver.find_element(By.XPATH,
                                                   '//*[@id="PDPOveriewLink"]/div[1]/div[2]/div[1]/div[2]/div/app-custom-product-summary/div/div/div[1]/app-custom-product-variants/div/app-custom-variant-selector/div/div[2]')
                url_elements = elements.find_elements(By.TAG_NAME, 'a')

                for url_element in url_elements:
                    url = url_element.get_attribute('href')
                    label = self.file_manager.get_name_from_url(url)
                    dict_url_models[label] = url.strip()
                break
            except Exception as e:
                if self.tracking_log:
                    if cnt_try + 1 == try_total:
                        print(f"Getting series error from {url}")
            finally:
                driver.quit()

        if self.tracking_log:
            print(f"SONY {self.file_manager.get_name_from_url(url)[4:]} series: {len(dict_url_models)}")
        for key, value in dict_url_models.items():
            if self.tracking_log:
                print(f'{key}: {value}')
        return dict_url_models


    def _get_global_spec(self, url: str) -> dict:
        """
        Extract global specifications from a given model URL.
        """
        try_total = 10
        model = None
        driver = None
        if self.tracking_log:  print(" Connecting to", url)
        for cnt_try in range(try_total):
            try:
                dict_spec = {}
                driver = self.web_driver.get_chrome()
                driver.get(url=url)
                time.sleep(self.wait_time)
                ## model name, price, descr
                description = driver.find_element(By.XPATH,
                                                  '//*[@id="PDPOveriewLink"]/div[1]/div[1]/div/app-custom-product-intro/div/h1/p').text
                model = driver.find_element(By.XPATH,
                                            '//*[@id="PDPOveriewLink"]/div[1]/div[1]/div/app-custom-product-intro/div/div/span').text
                try:
                    price_now = driver.find_element(By.XPATH,
                                                    '//*[@id="PDPOveriewLink"]/div[1]/div[2]/div[1]/div[2]/div/app-custom-product-summary/app-product-pricing/div/div[1]/p[1]').text
                    price_original = driver.find_element(By.XPATH,
                                                         '//*[@id="PDPOveriewLink"]/div[1]/div[2]/div[1]/div[2]/div/app-custom-product-summary/app-product-pricing/div/div[1]/p[2]').text
                    price_now = float(price_now.replace('$', '').replace(',', ''))
                    price_original = float(price_original.replace('$', '').replace(',', ''))
                    price_gap = price_original - price_now
                except:
                    price_now = ""
                    price_gap = ""
                    try:
                        price_now = driver.find_element(By.XPATH,
                                                        '//*[@id="PDPOveriewLink"]/div[1]/div[2]/div[1]/div[2]/div/app-custom-product-summary/app-product-pricing/div/div[1]/p').text
                        price_now = float(price_now.replace('$', '').replace(',', ''))
                    except:
                        if self.tracking_log:
                            print("no price")
                    finally:
                        price_original = price_now

                dict_spec["model"]=model.split(":")[-1].strip()
                dict_spec["description"] = description
                dict_spec["price"] = price_now
                dict_spec["price_original"] = price_original
                dict_spec["price_gap"] = price_gap
                dict_spec.update(self._extract_model_info(dict_spec.get("model")))

                ## model spec
                model = self.file_manager.get_name_from_url(url)
                dir_model = f"{self.log_dir}/{model}"
                stamp_today = self.file_manager.get_datetime_info(include_time=False)
                stamp_url = self.file_manager.get_name_from_url(url)

                if self.tracking_log:
                    self.file_manager.make_dir(dir_model)
                    driver.save_screenshot(f"./{dir_model}/{stamp_url}_0_model_{stamp_today}.png")
                time.sleep(self.wait_time)
                element_spec = driver.find_element(By.XPATH, '//*[@id="PDPSpecificationsLink"]')
                self.web_driver.move_element_to_center(element_spec)
                if self.tracking_log:
                    driver.save_screenshot(f"./{dir_model}/{stamp_url}_1_move_to_spec_{stamp_today}.png")
                time.sleep(self.wait_time)
                element_click_spec = driver.find_element(By.XPATH, '//*[@id="PDPSpecificationsLink"]/cx-icon')
                element_click_spec.click()
                time.sleep(self.wait_time)
                if self.tracking_log:
                    driver.save_screenshot(
                        f"./{dir_model}/{stamp_url}_2_after_click_specification_{stamp_today}.png")
                try:
                    element_see_more = driver.find_element(By.XPATH,'//*[@id="cx-main"]/app-product-details-page/div/app-product-specification/div/div[2]/div[3]/button')
                    self.web_driver.move_element_to_center(element_see_more)
                    if self.tracking_log:
                        driver.save_screenshot(f"./{dir_model}/{stamp_url}_3_after_click_see_more_{stamp_today}.png")
                    element_see_more.click()
                except:
                    try:
                        element_see_more = driver.find_element(By.XPATH,
                                                               '//*[@id="cx-main"]/app-product-details-page/div/app-product-specification/div/div[2]/div[2]/button')
                        self.web_driver.move_element_to_center(element_see_more)
                        if self.tracking_log:
                            driver.save_screenshot(
                                f"./{dir_model}/{stamp_url}_3_after_click_see_more_{stamp_today}.png")
                        element_see_more.click()
                    except:
                        if self.tracking_log:
                            print("Cannot find the 'see more' button on the page")
                time.sleep(self.wait_time)
                driver.find_element(By.ID, "ngb-nav-0-panel").click()
                for _ in range(15):
                    elements = driver.find_elements(By.CLASS_NAME,"full-specifications__specifications-single-card__sub-list")
                    for element in elements:
                        soup = BeautifulSoup(element.get_attribute("innerHTML"), 'html.parser')
                        dict_spec.update(self._soup_to_dict(soup))
                    ActionChains(driver).key_down(Keys.PAGE_DOWN).perform()
                if self.tracking_log:
                    driver.save_screenshot(f"./{dir_model}/{stamp_url}_4_end_{stamp_today}.png")
                if self.tracking_log:
                    print(f"Received information from {url}")
                return dict_spec
            except Exception as e:
                if self.tracking_log:
                    if cnt_try + 1 == try_total:
                        print(f"An error occurred on page 3rd : {model}")

            finally:
                driver.quit()
    def _extract_model_info(self, model):
        """
        Extract additional information from the model name.
        """
        dict_info = {}
        dict_info["year"] = model.split("-")[1][-1]
        dict_info["series"] = model.split("-")[1][2:-1]
        dict_info["size"] = model.split("-")[1][:2]
        dict_info["grade"] = model.split("-")[0]

        year_mapping = {
            'L': "2023",
            'K': "2022",
            'J': "2021",
            # Add additional mappings as needed
        }

        try:
            dict_info["year"] = year_mapping.get(dict_info.get("year"))
        except:
            dict_info["year"] = None

        return dict_info

    def _soup_to_dict(self, soup):
        """
        Convert BeautifulSoup soup to dictionary.
        """
        try:
            h4_tag = soup.find('h4').text.strip()
            p_tag = soup.find('p').text.strip()
        except :
            try:
                h4_tag = soup.find('h4').text.strip()
                p_tag = ""
            except Exception as e:
                print("Parser error", e)
                h4_tag = "Parser error"
                p_tag = "Parser error"
        return {h4_tag: p_tag}