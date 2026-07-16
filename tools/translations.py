# GPL License

# Thanks to https://www.thegrove3d.com/learn/how-to-translate-a-blender-addon/ for the idea

import os
import bpy
import json
import pathlib
import requests
from bpy.app.translations import locale

from .register import register_wrap
from . import settings

main_dir = pathlib.Path(os.path.dirname(__file__)).parent.resolve()
bundled_resources_dir = os.path.join(str(main_dir), "resources")
bundled_translations_dir = os.path.join(bundled_resources_dir, "translations")
addon_package = __package__.rpartition('.')[0]


def _user_storage_dir(path):
    try:
        return bpy.utils.extension_path_user(addon_package, path=path, create=True)
    except (AttributeError, ValueError):
        return bpy.utils.user_resource(
            'CONFIG', path=os.path.join("cats_blender_plugin", path), create=True
        )


resources_dir = _user_storage_dir("resources")
settings_file = os.path.join(resources_dir, "settings.json")
translations_dir = _user_storage_dir(os.path.join("resources", "translations"))

dictionary: dict[str, str] = dict()
languages = []
verbose = True
last_loaded_language = None
dictionary_download_link = "https://raw.githubusercontent.com/teamneoneko/Cats-Blender-Plugin-Unofficial-translations/5x-translations/dictionary.json"
_addon_startup_time = None


def _translation_directories():
    # User downloads override the immutable files bundled with the extension.
    return translations_dir, bundled_translations_dir


def _load_translation_dictionary(language):
    for directory in _translation_directories():
        candidate = os.path.join(directory, language + ".json")
        if not os.path.isfile(candidate):
            continue
        try:
            with open(candidate, 'r', encoding='utf-8') as file:
                messages = json.load(file).get("messages")
            if isinstance(messages, dict):
                return candidate, messages
        except (OSError, json.JSONDecodeError, AttributeError) as error:
            print(f"Could not load translation file {candidate}: {error}")
    return None, None


def _available_languages():
    available = []
    for directory in _translation_directories():
        if not os.path.isdir(directory):
            continue
        for filename in sorted(os.listdir(directory)):
            if filename.endswith(".json"):
                language = os.path.splitext(filename)[0]
                if language not in available:
                    available.append(language)
    return available

def load_translations(override_language=None):
    global dictionary, languages, last_loaded_language, _addon_startup_time
    import time

    # Set startup time on first load
    if _addon_startup_time is None:
        _addon_startup_time = time.time()

    dictionary = dict()
    languages = ["auto"]

    print("Loading translations")

    if override_language:
        language = override_language
        print(f"Using override language: {language}")
    else:
        language = get_language_from_settings()
        print(f"Selected language: {language}")

    # Get all current languages from user overrides and bundled defaults.
    languages.extend(_available_languages())
    print(f"Available languages: {languages}")

    # Determine the language to load
    language_to_load = language if language and language in languages else None

    # If language is not available, fallback to en_US
    if language_to_load is None:
        print(f"Language '{language}' not available, defaulting to en_US")
        language_to_load = "en_US"

    # Load the translation file
    translation_file, loaded_dictionary = _load_translation_dictionary(language_to_load)
    if translation_file:
        print(f"Loading translation file: {translation_file}")
        dictionary = loaded_dictionary
        last_loaded_language = language_to_load
        print(f"Loaded {len(dictionary)} translations from {language_to_load}")
    else:
        print(f"Translation file not found for language: {language_to_load}")
        # Load the default "en_US" translation file as last resort
        default_file, fallback_dictionary = _load_translation_dictionary("en_US")
        if default_file:
            print(f"Loading fallback translation file: {default_file}")
            dictionary = fallback_dictionary
            last_loaded_language = "en_US"
            print(f"Loaded {len(dictionary)} translations from en_US (fallback)")
        else:
            print("DEFAULT TRANSLATION FILE 'en_US.json' NOT FOUND.")

    check_missing_translations()


def t(phrase: str, *args, **kwargs):
    # Translate the given phrase into Blender's current language.
    output = dictionary.get(phrase)
    if output is None:
        if verbose:
            print('Warning: Unknown phrase: ' + phrase)
        return phrase

    return output.format(*args, **kwargs)


def check_missing_translations():
    for key, value in dictionary.items():
        if not value and verbose:
            print('Translations en_US: Value missing for key: ' + key)


def get_languages_list(self, context):
    choices = []

    for language in languages:
        # 1. Will be returned by context.scene
        # 2. Will be shown in lists
        # 3. will be shown in the hover description (below description)
        choices.append((language, language, language))

    return choices


def update_ui(self, context):
    global _addon_startup_time
    import time

    print("update_ui function called")

    # Don't trigger reload during the first 2 seconds after addon load (initialization period or crashes may occur)
    if _addon_startup_time and (time.time() - _addon_startup_time) < 2.0:
        print("Skipping reload during initialization period")
        return

    # Get the NEW language value directly from the scene property (not from file)
    # because the update callback is triggered BEFORE the settings file is saved
    current_language = context.scene.ui_lang if context and hasattr(context, 'scene') else None

    # Handle "auto" mode - detect from Blender locale
    if current_language and "auto" in current_language.lower():
        from bpy.app.translations import locale
        current_language = convert_locale_to_language_code(locale)
        if not current_language:
            current_language = "en_US"

    print(f"Current language from scene: {current_language}, Last loaded: {last_loaded_language}")

    if current_language != last_loaded_language:
        print(f"Language changed from {last_loaded_language} to {current_language}, reloading translations")

        # Save the settings first so get_language_from_settings() will return the new value
        settings.update_settings_core(None, None)

        load_translations()

        # Automatically reload scripts after a delay to apply new translations (old method was unreliable)
        def delayed_reload():
            try:
                print("Auto-reloading scripts to apply new language...")
                bpy.ops.script.reload()
                print("Language changed successfully!")
            except Exception as e:
                print(f"Script reload failed: {e}")
            return None

        # Delay by 2 seconds to ensure all dialogs are closed and operations complete (Or we get crashes due to gotchaes situation)
        bpy.app.timers.register(delayed_reload, first_interval=2.0)
    else:
        print("Language unchanged, no reload needed")


def get_language_from_settings():
    # Load settings file
    settings_source = settings_file
    bundled_settings_file = getattr(
        settings, 'bundled_settings_file', os.path.join(bundled_resources_dir, "settings.json")
    )
    if not os.path.isfile(settings_source) and os.path.isfile(bundled_settings_file):
        settings_source = bundled_settings_file
    try:
        with open(settings_source, encoding="utf8") as file:
            settings_data = json.load(file)
    except FileNotFoundError:
        print("SETTINGS FILE NOT FOUND!")
        return
    except json.decoder.JSONDecodeError:
        print("ERROR FOUND IN SETTINGS FILE")
        return

    if not settings_data:
        print("NO DATA IN SETTINGS FILE")
        return

    lang = settings_data.get("ui_lang")
    if not lang or "auto" in lang.lower():
        # Auto-detect language from Blender's locale
        from bpy.app.translations import locale as current_locale
        detected_lang = convert_locale_to_language_code(current_locale)
        print(f"Auto-detecting language from Blender locale: {current_locale} -> {detected_lang}")
        return detected_lang

    return lang


def convert_locale_to_language_code(blender_locale):
    """
    Convert Blender's locale format to supported language code format.
    Blender uses formats like 'en_US', 'ja_JP', 'ko_KR', etc.
    """
    if not blender_locale:
        return None

    # Blender locale is already in the format we need (e.g., 'en_US')
    locale_str = str(blender_locale)

    # Check if exact match exists in available languages
    for lang_code in _available_languages():
        if locale_str == lang_code:
            print(f"Found exact locale match: {lang_code}")
            return lang_code

    # Try to match by language code (first part before underscore)
    language_only = locale_str.split("_")[0].lower() if "_" in locale_str else locale_str.lower()
    for lang_code in _available_languages():
        if lang_code.lower().startswith(language_only):
            print(f"Found language match: {lang_code}")
            return lang_code

    # Fallback to English if no match
    print(f"No language match found for locale: {locale_str}, defaulting to en_US")
    return None

@register_wrap
class DownloadTranslations(bpy.types.Operator):
    bl_idname = 'cats_translations.download_latest'
    bl_label = 'Download Latest Translations'
    bl_description = 'Download the latest translations for cats UI and internal dictionary'   
    bl_options = {'INTERNAL'}

    def execute(self, context):
        if not bpy.app.online_access:
            self.report({'ERROR'}, "Online access is disabled in Blender's preferences")
            return {'CANCELLED'}

        # GitHub repository and folder information
        repo_owner = "teamneoneko"
        repo_name = "Cats-Blender-Plugin-Unofficial-translations"
        branch = "5x-translations"
        folder_path = "UI%20Tanslations"

        # Construct the API URL to get the list of files in the folder
        api_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/contents/{folder_path}?ref={branch}"

        try:
            # Send a GET request to the API URL
            response = requests.get(
                api_url,
                headers={"Accept": "application/vnd.github+json", "User-Agent": "Cats-Blender-Plugin"},
                timeout=30,
            )
            response.raise_for_status()  # Raise an exception if the request was unsuccessful

            # Parse the JSON response
            files = response.json()
            if not isinstance(files, list):
                raise ValueError("GitHub returned an unexpected translation file listing")

            # Download each translation file
            for file_info in files:
                if not isinstance(file_info, dict):
                    continue
                file_name_remote = file_info.get("name", "")
                if file_info.get("type") == "file" and file_name_remote.endswith(".json"):
                    file_url = file_info.get("download_url")
                    if not file_url:
                        continue
                    file_name = os.path.basename(file_name_remote)
                    file_path = os.path.join(translations_dir, file_name)

                    # Download the translation file
                    file_response = requests.get(file_url, timeout=30)
                    file_response.raise_for_status()
                    translation_data = file_response.content
                    translation_json = json.loads(translation_data.decode('utf-8'))
                    if not isinstance(translation_json, dict) or not isinstance(
                        translation_json.get('messages'), dict
                    ):
                        raise ValueError(f"Downloaded translation is invalid: {file_name}")

                    # Save the translation file
                    temporary_file = file_path + ".tmp"
                    with open(temporary_file, 'wb') as file:
                        file.write(translation_data)
                    os.replace(temporary_file, file_path)

                    print(f"Downloaded: {file_name}")

        except (requests.exceptions.RequestException, OSError, ValueError, json.JSONDecodeError) as e:
            print("TRANSLATIONS FILES COULD NOT BE DOWNLOADED")
            self.report({'ERROR'}, "TRANSLATIONS FILES COULD NOT BE DOWNLOADED: " + str(e))
            return {'CANCELLED'}

        print('TRANSLATIONS DOWNLOAD FINISHED')

        # Define the dictionary file path
        dictionary_file = os.path.join(resources_dir, "dictionary.json")

        # Download dictionary.json from GitHub
        print('DOWNLOAD DICTIONARY FILE')
        try:
            response = requests.get(dictionary_download_link, timeout=30)
            response.raise_for_status()  # Raise an exception if the request was unsuccessful
            dictionary_data = response.content
            if not isinstance(json.loads(dictionary_data.decode('utf-8')), dict):
                raise ValueError("Downloaded translation dictionary is invalid")
            temporary_file = dictionary_file + ".tmp"
            with open(temporary_file, 'wb') as file:
                file.write(dictionary_data)
            os.replace(temporary_file, dictionary_file)
        except (requests.exceptions.RequestException, OSError, ValueError, json.JSONDecodeError) as e:
            print("DICTIONARY FILE COULD NOT BE DOWNLOADED")
            self.report({'ERROR'}, "DICTIONARY FILE COULD NOT BE DOWNLOADED: " + str(e))
            return {'CANCELLED'}
        print('DICTIONARY DOWNLOAD FINISHED')

        bpy.ops.script.reload()

        self.report({'INFO'}, "Successfully downloaded the translations and dictionary")
        return {'FINISHED'}




load_translations()
