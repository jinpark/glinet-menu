import AppKit
import Foundation
import json
import rumps
# rumps.debug_mode(True)

from wrapt_timeout_decorator import *
import os
from pyglinet import GlInet, exceptions

SENTRY_ENABLED = os.environ.get("SENTRY_ENABLED", "false").lower() == "true"
if SENTRY_ENABLED:
    from sentry_sdk import capture_exception, init
    init(
        dsn=os.environ.get("SENTRY_DSN"),
        traces_sample_rate=1.0,
        profiles_sample_rate=1.0,
        enable_tracing=True,
    )

DEFAULT_CONFIG = {
                  'url': 'https://192.168.8.1/rpc',
                  'username': 'root'
                 }

def capture_sentry_exception(e):
    if SENTRY_ENABLED:
        capture_exception(e)

class GlinetWireguardClientChanger(rumps.App):  
    def __init__(self):
        super(GlinetWireguardClientChanger, self).__init__("Glinet")
        self.icon = "glinet-fav.png"
        self.login_password_file = os.path.join(rumps.application_support("glinet-wg-client-changer"), "login_password.txt")
        self.config_file = os.path.join(rumps.application_support("glinet-wg-client-changer"), "config.json")
        self.router_config = self.get_router_config()
        self.online = False
        self.current_wg = None
        self.online_button = None
        self.first_run = True
        self.menu.clear()
        self.try_login()

    def get_router_config(self):
        if os.path.exists(self.config_file):
            try: 
                file = open(self.config_file, "r")
                content = file.read()
                return json.loads(content)
            except Exception as e:
                print('get router config error')
                print(e)
                capture_sentry_exception(e)
                return DEFAULT_CONFIG
        else:
            return DEFAULT_CONFIG

    @timeout(2.5)
    def try_login(self):
        if os.path.exists(self.login_password_file):
            password_file = open(self.login_password_file, "r")
            password = password_file.read()
            try: 
                self.glinet = GlInet(url=self.router_config["url"], username=self.router_config["username"], password=password, keep_alive=False, cache_folder=rumps.application_support("glinet-wg-client-changer"), skip_api_reference=True)
                self.glinet.login()
            except Exception as e:
                print('error')
                print(e)
                capture_sentry_exception(e)
                rumps.alert(None, "password or config is incorrect. please check the config or enter password again", icon_path="glinet-fav.png")
                self.reset_menu()
                return False
            try:
                self.after_login()
                self.update_active_peer_in_menu()
                self.first_run = False
                return True
            except Exception as e:
                print('error after login pass')
                print(e) 
                capture_sentry_exception(e)
                self.reset_menu()
                return False
        else:
            print('no password file')
            self.reset_menu()
            return False

    def after_login(self):
        self.menu.clear()
        self.configs = self.glinet.request("call",["wg-client", "get_all_config_list"])["result"]["config_list"]
        self.groups = self.create_groups(self.configs)
        self.peer_list = self.create_peer_list(self.groups, self.configs)
        menu = [self.create_setting_menu()] + [None] +  self.create_group_menus(self.groups) + [None]
        if not self.first_run:
            menu = menu + [self.quit_button]
        self.menu = menu

    def logout(self, _sender):
        print("logout")
        self.glinet.logout()
        os.remove(self.login_password_file)
        self.reset_menu()
        self.online = False
    
    def reset_menu(self):
        self.menu.clear()
        if self.first_run:
            self.menu = [rumps.MenuItem("Config", callback=self.update_router_info), rumps.MenuItem("Login", callback=self.enter_password)]
        else:
            self.menu = [rumps.MenuItem("Config", callback=self.update_router_info), rumps.MenuItem("Login", callback=self.enter_password), self.quit_button]
        self.first_run = False
        

    # @rumps.timer(5)
    # def online_check(self, sender=None):
    #     if self.online_button != None: 
    #         try: 
    #             is_alive = self.glinet.is_alive()
    #             if is_alive:
    #                 self.online_button.state = 1
    #                 self.online = True
    #             else:
    #                 self.online_button.state = 0
    #                 self.online = False
    #         except Exception as e:
    #             print('online check error')
    #             print(e)
    #             self.online_button.state = 0
    #             self.online = False

    def enter_password(self, sender):
        window = rumps.Window("enter router login password", "Login", default_text="", icon_path="glinet-fav.png")
        window._textfield = AppKit.NSSecureTextField.alloc().initWithFrame_(Foundation.NSMakeRect(0, 0, 200, 25))
        window._alert.setAccessoryView_(window._textfield)
        window._alert.window().setInitialFirstResponder_(window._textfield)
        response = window.run()
        with open(self.login_password_file, 'w') as writefile:
            writefile.write(response.text)
        try: 
            self.try_login()
        except:
            capture_sentry_exception(e)
            rumps.alert(None, "password or config is incorrect. please try logging in again", icon_path="glinet-fav.png")

    def update_active_peer_in_menu(self):
        self.current_wg = self.get_current_wg()
        for item in self.menu.items():
            if not isinstance(item[1], rumps.rumps.SeparatorMenuItem):
                for subitem in item[1].items():
                    if isinstance(subitem[1], rumps.MenuItem):
                        if subitem[0] == self.current_wg["name"]:
                            subitem[1].state = 1
                        else:
                            subitem[1].state = 0
                

    def get_current_wg(self):
        config_status = self.glinet.request("call",["wg-client", "get_status"] )
        print("current")
        print(config_status["result"])
        return config_status["result"]

    def create_groups(self, configs):
        groups = {}
        for config in configs:
            if len(config["peers"]) != 0:
                groups[config["group_id"]] = config
        return groups

    def create_peer_list(self, groups, configs):
        peer_list = {}
        for config in configs:
            for peer in config["peers"]:
                peer["group_name"] = groups[config["group_id"]]["group_name"]
                peer["group_id"] = config["group_id"]
                peer_list[peer["name"]] = peer
        return peer_list


    def switch_wireguard_peer(self, conf):
        conf = self.peer_list[conf.title]
        success = False
        try:
            resp = self.glinet.request("call",["wg-client", "start", {'group_id': conf["group_id"], 'peer_id': conf["peer_id"], 'name': conf["name"]}] )
            self.update_active_peer_in_menu()
            success = True
        except exceptions.NotLoggedInError: 
            self.try_login()
            resp = self.glinet.request("call",["wg-client", "start", {'group_id': conf["group_id"], 'peer_id': conf["peer_id"], 'name': conf["name"]}] )
            self.update_active_peer_in_menu()
            success = True
        if success:
            rumps.notification(title="Active Wireguard Updated", subtitle="Updated to " + conf["name"], message="", sound=False, icon="glinet-fav.png", action_button=False, other_button=False)

    def create_group_menus(self, groups):
        group_menu_items = []
        for group_id in groups.keys():
            group_menu = rumps.MenuItem(groups[group_id]["group_name"])
            for peer in groups[group_id]["peers"]:
                config_menu = rumps.MenuItem(peer["name"], callback=self.switch_wireguard_peer)
                group_menu.add(config_menu)
            group_menu_items.append(group_menu)
        return group_menu_items
    
    def update_router_info(self, sender):
        print('update router info') 
        content = json.dumps(DEFAULT_CONFIG)
        if os.path.exists(self.config_file):
            file = open(self.config_file, "r")
            content = file.read()
            try:
                json.loads(content)
            except Exception as e:
                capture_sentry_exception(e)
                content = json.dumps(DEFAULT_CONFIG)
        else:
            print('content')
            print(content)
            with open(self.config_file, 'w') as writefile:
                writefile.write(content)
        window = rumps.Window("Modify the url (usually the standard router url but with '/rpc') and the username if you have changed it from root.", "Router Configuration", default_text=content, icon_path="glinet-fav.png")
        # window._textfield = AppKit.NSSecureTextField.alloc().initWithFrame_(Foundation.NSMakeRect(0, 0, 200, 25))
        # window._alert.setAccessoryView_(window._textfield)
        # window._alert.window().setInitialFirstResponder_(window._textfield)
        response = window.run()
        try:
            with open(self.config_file, 'w') as writefile:
                writefile.write(response.text)
            self.router_config = json.loads(response.text)
        except Exception as e:
            print('save config error')
            print(e)
            print(response.text)
            rumps.alert(None, "invalid json format. Please try again", icon_path="glinet-fav.png")
            return
    
    def about(self, sender):
        rumps.alert("Glinet Wireguard Client Changer", "A simple menu bar app to change active wireguard peer on a gl-inet router\nEmail me at jin@smugdeveloper.com if there are any issues!\n", icon_path="glinet-fav.png")

    def create_setting_menu(self):
        setting_menu = rumps.MenuItem("Settings")
        # self.online_button = rumps.MenuItem("Online", callback=None)
        # setting_menu.add(self.online_button)
        # self.router_info = rumps.MenuItem("Config", callback=self.update_router_info)
        # setting_menu.add(self.router_info)
        setting_menu.add(rumps.MenuItem("About", callback=self.about))
        setting_menu.add(rumps.MenuItem("Logout", callback=self.logout))
        return setting_menu

if __name__ == "__main__":
    GlinetWireguardClientChanger().run()