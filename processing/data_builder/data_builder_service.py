from threading import Event

from PySide6.QtCore import QObject, Signal

from result_data_builder.result_data_builder import ResultDataBuilder
from tools.nanoparticle_shape.nps_service import NanoParticleShapeService


class SampleBuilderService(QObject):
    particules_processed = Signal(int)

    def __init__(self,
                 base_builder: ResultDataBuilder,
                 nps_service: NanoParticleShapeService,
                 /,
                 parent=None):
        super().__init__(parent=parent)
        self.stop_build = Event()  # For thread safety
        self.nps_service: NanoParticleShapeService = nps_service
        self.base_builder: ResultDataBuilder = base_builder

    def build_particules(self, particles):
        """
        Args:
            particles:
        Returns:

        """
        self.stop_build.clear()
        self._build_chain_of_responsibility()
        self._init_chain_of_responsibility()

        self.particules_processed.emit(0)
        for i, particle in enumerate(particles):
            if self.stop_build.is_set():
                return
            self.base_builder.build_on(particle)

            # Not emitted every time because of the overhead cost.
            if i % 400 == 0:
                self.particules_processed.emit(i)

    def _build_chain_of_responsibility(self):
        pass

    def _init_chain_of_responsibility(self):
        self.base_builder.init()

    def cancel_build(self):
        """
        This method stops the ``build_particules`` method.
        Notes:
            The currently processed particule will be completed before stoping.
        """
        self.stop_build.set()

    def set_current_sample(self, current_sample: str):
        # TODO: Maybe more class related.
        if hasattr(self.base_builder, "current_sample"):
            self.base_builder.current_sample = current_sample
