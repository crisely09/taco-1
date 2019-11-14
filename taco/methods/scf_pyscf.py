"""
HF method using PySCF.
"""

import numpy as np
from copy import copy
from pyscf import scf, gto, dft
from taco.methods.scf import ScfMethod


def get_pyscf_molecule(mol, basis):
    """Generate PySCF molecule object.
    Parameters
    ----------
    mol : qcelemental.models.Molecule
        The molecule object.
    """
    if not hasattr(mol, 'molecular_multiplicity'):
        raise AttributeError("Molecule must have multiplicity.")
    multiplicity = mol.molecular_multiplicity
    spin = multiplicity - 1
    string = mol.to_string(dtype='xyz')
    lines = string.splitlines()
    count = 0
    for line in lines:
        if len(line.split(' ')) < 4:
            count += 1
    string = '\n'.join(lines[count:])
    pyscf_mol = gto.M(
            atom=string,
            basis=basis,
            spin=spin,)
    return pyscf_mol


class ScfPyScf(ScfMethod):
    """Base class for method objects.

    Attributes
    ----------
    density : list[np.ndarray(dtype=float)]
        List with densities obtained with this method.
    energy : dict('name', np.ndarray)
        Energies obtained with this method.

    Properties
    ----------
    restricted : bool
        Wheter the wavefunction is restricted or not.

    Methods
    ---------
    __init__(self, mol)
        Initialize the method.
    get_density(self) :
        Return density/densities.
    get_energy(self) :
        Return final SCF energy/energies.
    get_fock(self) :
        Return Fock matrix.
    solve_scf :
        Perform the SCF calculation.
    perturb_fock(self, pot) :
        Add a potential to the Fock matrix.

    """
    def __init__(self, mol, basis, method, xc_code=None):
        """ ScfPyScf object.

        Parameters
        ----------
        mol : qcelemental Molecule object
            Molecule information.
        basis : string
            Name of the basis set to be used.
        method : string
            Type of SCF method. Available options are:`hf` or `dft`.
        xc_code : string
            Only needed for DFT.
        """
        ScfMethod.__init__(self, mol)
        self.mol_pyscf = get_pyscf_molecule(self.mol, basis)
        if self.restricted:
            if method.lower() == 'dft':
                if xc_code is None:
                    raise ValueError('DFT functional not specified.')
                self.scf_object = dft.RKS(self.mol_pyscf)
                self.scf_object.xc = xc_code
            elif method.lower() == 'hf':
                self.scf_object = scf.RHF(self.mol_pyscf)
            else:
                raise ValueError("Unknown method {}.".format(method))
        else:
            # Unrestricted case not implemented
            raise NotImplementedError("Unrestricted SCF not implemented.")
        # Keep a clean copy of the scf object for latter
        self._scf_object = copy(self.scf_object)

    def get_fock(self):
        """Return Fock matrix."""
        return self.scf_object.get_fock()

    def perturb_fock(self, pot):
        """Add an effective potential to the Fock matrix.

        Parameters
        ----------
        pot : np.ndarray(dtype=float)
            Effective potential in the form of a Fock matrix.

        """
        if not isinstance(pot, np.ndarray):
            raise TypeError("The potential should be given as np.ndarray.")
        ref = self.scf_object.get_hcore()
        pot += ref
        # Override function
        self.scf_object.get_hcore = lambda *args: pot

    def restore_scf_object(self):
        """Recover initial configuration."""
        self.scf_object = copy(self._scf_object)

    def solve_scf(self, **scfkwargs):
        """Perform SCF calculation.

        Kwargs
        ------
        conv_tol : float
            converge threshold.
        conv_tol_grad : float
            gradients converge threshold.
        dump_chk : bool
            Whether to save SCF intermediate results in the checkpoint file
        dm0 : ndarray
            Initial guess density matrix.  If not given (the default), the kernel
            takes the density matrix generated by ``mf.get_init_guess``.
        callback : function(envs_dict) => None
            callback function takes one dict as the argument which is
            generated by the builtin function :func:`locals`, so that the
            callback function can access all local variables in the current
            envrionment.

        """
        for attr in scfkwargs:
            self.scf_object.attr = scfkwargs[attr]
        self.scf_object.kernel()
        self.energy["scf"] = self.scf_object.e_tot
        self.density = self.scf_object.make_rdm1()
