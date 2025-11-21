import requests
import json
import base64
import time
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any, Union
import random
import re


class PromptGenerator:
    def __init__(self, resources_dir: str = "resources"):
        self.resources_dir = Path(resources_dir)
        self.replacements = self._load_resources()

    def _load_resources(self) -> Dict[str, List[str]]:
        replacements = {}
        resource_files = {
            "r_color": "r_color.txt",
            "r_artist": "r_artist.txt",
            "r_place": "r_place.txt",
            "r_style": "r_style.txt",
            "r_action": "r_action.txt",
            "r_object": "r_object.txt",
            "f_anime": "f_anime.txt",
            "m_anime": "m_anime.txt",
            "r_light": "r_light.txt",
            "r_angle": "r_angle.txt",
        }

        for key, filename in resource_files.items():
            file_path = self.resources_dir / filename
            if file_path.exists():
                # utf with bom
                with open(file_path, "r", encoding="utf-8-sig") as f:
                    replacements[key] = [line.strip() for line in f if line.strip()]
            else:
                replacements[key] = [f"!{key.upper()}!"]

        return replacements

    def generate(self, template: str) -> str:
        pattern = re.compile(
            r"\b(r_color|r_artist|r_place|r_style|r_action|r_object|f_anime|m_anime|r_light|r_angle)\b"
        )

        def replace_match(match):
            key = match.group(1)
            values = self.replacements.get(
                key, [f"!{key.upper()}!"]
            )  # Fallback if key not found, though unlikely
            formatted_values = "|".join(values)
            return f"{{{formatted_values}}}"

        replaced_template = pattern.sub(replace_match, template)
        final = replaced_template
        return final


# Data classes para los scripts alwayson
@dataclass
class ADetailerArgs:
    ad_model: str = "face_yolov8n.pt"
    ad_mask_blur: int = 6
    # ad_confidence: float = 0.3
    # ad_denoising_strength: float = 0.3
    # ad_inpaint_only_masked: bool = True
    ad_inpaint_only_masked_padding: int = 64
    # ad_use_inpaint_width_height: bool = True
    ad_inpaint_width: int = 832
    ad_inpaint_height: int = 1216


@dataclass
class AlwaysOnScripts:
    ADetailer: Dict[str, Any] = field(
        default_factory=lambda: {
            "args": [
                ADetailerArgs().__dict__,
            ]
        }
    )


# Data classes base
@dataclass
class BasePayload:
    prompt: str
    negative_prompt: str
    steps: int = 8
    width: int = 832
    height: int = 1216
    cfg_scale: float = 1
    distilled_cfg_scale: float = None
    sampler_name: str = "Euler"
    scheduler: str = "Simple"
    seed: int = -1
    n_iter: int = 1
    batch_size: int = 1
    alwayson_scripts: Dict[str, Any] = field(default_factory=AlwaysOnScripts().__dict__)


    def __post_init__(self):
        for key in list(self.__dict__.keys()):
            if getattr(self, key) is None:
                delattr(self, key)

@dataclass
class Txt2ImgPayload(BasePayload):
    enable_hr: bool = field(default=False)
    denoising_strength: float = field(default=0.15)
    hr_scale: float = field(default=1.5)
    # hr_negative_prompt: str = "",
    # hr_cfg: float = 1.0
    hr_additional_modules: list = field(default_factory=list)  # Corregido aquí
    hr_upscaler: str = field(default="R-ESRGAN 4x+")
    hr_second_pass_steps: int = field(default=0)



    def __post_init__(self):
        super().__post_init__()
        self.hr_cfg = self.cfg_scale
        if self.hr_second_pass_steps == 0:
            self.hr_second_pass_steps = int(self.steps / 2)
        if hasattr(self, "distilled_cfg_scale"):
            if self.distilled_cfg_scale is not None:
                self.hr_distilled_cfg = self.distilled_cfg_scale
                self.cfg_scale = 1.

            else:
                try:
                    delattr(self, "distilled_cfg_scale")  # Quita el espacio en el nombre
                except Exception:
                    pass

    @classmethod
    def from_template(cls, template: str, generator: PromptGenerator, **kwargs):
        processed_prompt = generator.generate(template)
        return cls(prompt=processed_prompt, **kwargs)


@dataclass
class Img2ImgPayload(BasePayload):
    init_images: List[str] = field(default_factory=list)
    denoising_strength: float = 0.75
    resize_mode: int = 0
    inpaint_full_res: bool = True
    inpainting_mask_invert: int = 0


class A1111Client:
    def __init__(self, base_url: str, output_dir: str = "outputs"):
        self.base_url = base_url.rstrip("/")
        self.output_dir = Path(output_dir)
        self._create_directories()

        self.endpoints = {
            "txt2img": f"{self.base_url}/sdapi/v1/txt2img",
            "img2img": f"{self.base_url}/sdapi/v1/img2img",
            "extras": f"{self.base_url}/sdapi/v1/extras",
            "progress": f"{self.base_url}/sdapi/v1/progress",
            "options": f"{self.base_url}/sdapi/v1/options",
        }
        
    def set_flux_options(self):
        payload = {
            # "forge_preset": "flux",
            # "forge_inference_memory": 7168,
            # "forge_async_loading": "Queue",
            # "forge_pin_shared_memory": "CPU"
            "CLIP_stop_at_last_layers": 2
        }
        response = requests.post(
            self.endpoints["options"], json=payload
        )
        actual = requests.get(self.endpoints["options"])
        result = self._handle_response(actual)
        print(actual)
    
    
    def set_xl_options(self):
        payload = {
            # "forge_preset": "xl",
            # "forge_inference_memory": 1024,
            # "forge_async_loading": "Queue",
            # "forge_pin_shared_memory": "CPU"
            "CLIP_stop_at_last_layers": 2
        }
        response = requests.post(
            self.endpoints["options"], json=payload
        )
        actual = requests.get(self.endpoints["options"])
        result = self._handle_response(actual)
        print(actual)

    def _create_directories(self):
        (self.output_dir / "txt2img").mkdir(parents=True, exist_ok=True)
        (self.output_dir / "img2img").mkdir(parents=True, exist_ok=True)

    def _save_images(self, images: List[str], subdir: str, prefix: str = "image"):
        output_paths = []
        timestamp = int(time.time())
        save_dir = self.output_dir / subdir

        for i, img_data in enumerate(images):
            filename = f"{prefix}_{timestamp}_{i}.png"
            file_path = save_dir / filename

            with open(file_path, "wb") as f:
                f.write(base64.b64decode(img_data.split(",", 1)[0]))

            output_paths.append(file_path)

        return {"paths": output_paths, "images": images}

    def _handle_response(self, response: requests.Response) -> Dict:
        if response.status_code != 200:
            raise Exception(f"API Error: {response.status_code} - {response.text}")

        json_data = response.json()
        with open("info.json", "w", encoding="utf-8") as f:
            json.dump(json_data, f, ensure_ascii=False, indent=4)
        return json_data

    def get_progress(self, skip_current_image: bool = False) -> Dict:
        """Obtiene el progreso actual de la generación"""
        params = {"skip_current_image": json.dumps(skip_current_image)}
        response = requests.get(self.endpoints["progress"], params=params)
        return self._handle_response(response)

    def txt2img_with_progress(
        self,
        payload: Txt2ImgPayload,
        interval: float = 1.0,
        callback: Optional[callable] = None,
    ) -> List[Path]:
        """Versión con seguimiento de progreso"""
        import threading

        # Guardar payload y preparar resultado
        with open("payload.json", "w") as f:
            f.write(json.dumps(payload.__dict__))

        result_container = []
        exception_container = []

        # Hilo para la generación
        def generate():
            try:
                response = requests.post(
                    self.endpoints["txt2img"], json=payload.__dict__
                )
                result = self._handle_response(response)
                result_container.extend(
                    self._save_images(result.get("images", []), "txt2img")
                )
                print(result_container)
            except Exception as e:
                exception_container.append(e)

        # Iniciar generación en segundo plano
        thread = threading.Thread(target=generate)
        thread.start()

        # Monitorear progreso
        while thread.is_alive():
            progress = self.get_progress()
            if callback:
                callback(progress)
            time.sleep(interval)

        if exception_container:
            raise exception_container[0]

        return result_container

    def txt2img(self, payload: Txt2ImgPayload):
        payload_dict = asdict(payload)
        payload_dict = {k: v for k, v in payload_dict.items() if v is not None}
        print(payload_dict)
        with open("payload.json", "w") as f:
            f.write(json.dumps(payload_dict))
        if hasattr(payload_dict, "distilled_cfg_scale"):
            print("Tiene distilled nada q ver")
            self.set_flux_options()
        else:
            self.set_xl_options()
        response = requests.post(self.endpoints["txt2img"], json=payload_dict)
        result = self._handle_response(response)
        images = result.get("images", [])
        info = json.loads(result["info"])
        final = self._save_images(images, "txt2img")
        return {
            "images": images,
            "paths": final["paths"],
            "payload": payload,
            "info": info,
        }

    def img2img(self, payload: Img2ImgPayload) -> List[Path]:
        response = requests.post(self.endpoints["img2img"], json=payload.__dict__)
        result = self._handle_response(response)
        return self._save_images(result.get("images", []), "img2img")

    def get_samplers(self) -> List[Dict]:
        response = requests.get(f"{self.base_url}/sdapi/v1/samplers")
        return self._handle_response(response)

    def get_models(self) -> List[str]:
        response = requests.get(f"{self.base_url}/sdapi/v1/sd-models")
        return [model["title"] for model in self._handle_response(response)]


def progress_callback(data: dict):
    print(
        f"Progreso: {data.get('progress', 0) * 100:.1f}% | ETA: {data.get('eta_relative', 0):.1f}s"
    )
    if data.get("current_image"):
        # Podrías decodificar y mostrar la imagen preview aquí
        pass


# Ejemplo de uso mejorado
if __name__ == "__main__":
    client = A1111Client("https://rnaje-34-32-187-60.a.free.pinggy.link")
    # Configura el generador (asegúrate de tener los archivos en resources/)
    prompt_gen = PromptGenerator()

    # Plantilla con placeholders
    # Gorgeous long r_color haired empress, r_color hairpins and fringe, goddess of peach,wearing a small light r_color and r_color r_color dress, wearing a tanzanite collar, holding a golden chest full of pearls, r_action between pink flowers Japanese garden, r_artist
    while True:
        template = input("Introduce un prompt: ")

        if not template:
            print("Saliendo.")
            exit(1)

        # Configuración personalizada de ADetailer
        adetailer_args = [
            ADetailerArgs(ad_model="face_yolov8n.pt", ad_confidence=0.3),
            ADetailerArgs(ad_model="hand_yolov8n.pt", ad_confidence=0.3),
        ]

        payload = Txt2ImgPayload.from_template(
            template=template,
            generator=prompt_gen,
            negative_prompt="Naked, Nude, fake eyes, deformed eyes, bad eyes, cgi, 3D, digital, airbrushed",
            steps=12,
            width=832,
            height=1216,
            cfg_scale=5,
            enable_hr=False,
            n_iter=4,
            hr_upscaler="4x-UltraSharp",
            alwayson_scripts={},
            # alwayson_scripts=AlwaysOnScripts(
            #     ADetailer={"args": [args.__dict__ for args in adetailer_args]}
            # ).__dict__,f
        )

        try:
            saved_images = client.txt2img_with_progress(
                payload, interval=5, callback=progress_callback
            )
            print(f"Imágenes guardadas: {saved_images}")
        except Exception as e:
            print(f"Error: {e}")
