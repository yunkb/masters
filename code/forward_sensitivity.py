from dolfin import *
from numpy import fliplr, linspace, inf
from os.path import join as osjoin
from scipy.io import loadmat as sc_io_loadmat
from scipy.interpolate import RegularGridInterpolator
import sys
import matplotlib.pyplot as plt
import matplotlib.cm as cm
from matplotlib import colors

set_log_level(ERROR) 

class InterpolatedParameter(Expression):
    '''
        Class to get tumor cell distributions by interpolating based off matrices of tumor cell data
    '''
    def __init__(self,X,Y,image,**kwargs):
        self.X = X # A numpy array giving the X-spacing of the image
        self.Y = Y # Same for Y
        self.image = image # The image of measured material property    
    def eval_cell(self,values,x,cell):
        interp_handle = RegularGridInterpolator((self.X,self.Y),self.image)
        values[0] = interp_handle(x)
        
def interp(file_loc,mat_name):
    """
        Function to accept matlab .mat file with tumor data and interpolate values onto mesh
    """
    mat = sc_io_loadmat(file_loc)[mat_name]
    mat = fliplr(mat.T)/theta  # Needs to be adjusted to fit the mesh correctly; scaled
    x,y = mat.shape[0], mat.shape[1]
    mat_interp = InterpolatedParameter(linspace(1,x,x),linspace(1,y,y),mat,degree=1)
    return interpolate(mat_interp,V)

def param_update(nonlinear_solver):
    prm1 = nonlinear_solver.parameters
    prm1['newton_solver']['absolute_tolerance'] = 1E-7
    prm1['newton_solver']['relative_tolerance'] = 1E-6
    prm1['newton_solver']['maximum_iterations'] = 51
    prm1['newton_solver']['relaxation_parameter'] = 1.0
    prm1['newton_solver']['linear_solver'] = 'gmres'
    prm1['newton_solver']['preconditioner'] = 'ilu'
    prm1['newton_solver']['krylov_solver']['absolute_tolerance'] = 1E-8
    prm1['newton_solver']['krylov_solver']['relative_tolerance'] = 1E-6
    prm1['newton_solver']['krylov_solver']['maximum_iterations'] = 1000
    prm1['newton_solver']['krylov_solver']['nonzero_initial_guess'] = True
    return None

def recorder(variables,names,name,t):
    for i, var in enumerate(variables):
        var.rename(names[i]+'_'+name,names[i])
        f_notime.write(var,t)
    return None

def forward(initial_p, name=None):    
    """ 
        Here, we define the forward problem. 
    """
    '''
        - E(u) returns the Green-Lagrange strain tensor
        - sigma(...) returns the actual stress tensor
        - sigma_form(...) returns the stress tensor based on the cells (phi), elasticity coefficients, and a coefficient beta
        - vonmises(...) calculates the von Mises stress based on the actual stress tensor
    '''
    global t
    
    ## Define functions
    I = Identity(2)  # Identity tensor
    def E(u):
        return 0.5*(nabla_grad(u) + nabla_grad(u).T)
    def vonmises(u):
        s = sigma(u) - (1./2)*tr(sigma(u))*I  # deviatoric stress
        von_Mises = sqrt(3./2*inner(s, s))
        return project(von_Mises, V)

    # Set up problem
    U    = VectorFunctionSpace(mesh,'Lagrange',1)
    def boundary(x, on_boundary):
        return on_boundary
    bc   = DirichletBC(U, Constant((0.,0.)), boundary)
    p_n = interpolate(initial_p,V)
    v    = TestFunction(U)
    
    ffc_options = {"quadrature_degree": 2, "cpp_optimize": True}
    parameters['form_compiler']['quadrature_degree'] = 2
    parameters['form_compiler']['cpp_optimize'] = True
    parameters['krylov_solver']['nonzero_initial_guess'] = True
    
    if lin_hyp == 0:
        def sigma(u):
            s = 2*mu*E(u)+lmbda*tr(E(u))*I
            return s
        u    = TrialFunction(U)
        a = inner(2*mu*E(u)+lmbda*tr(E(u))*I,E(v))*dx
        L = inner(2*beta*p_n*I*(mu+lmbda),E(v))*dx
        u    = Function(U)
        def mech():
            solve(a == L, u, bc, 
                      form_compiler_parameters=ffc_options)
            return u
    else:
        def sigma(u):
            F = I + grad(u)             # Deformation gradient
            B = F*F.T
            C = F.T*F
            J = det(F)
            I1 = tr(C)
            s = lmbda*(J-1)*I+mu*(B-1./2*I1*I)/(J**(5./3))
            return s
        def sigma_form(u, phi):
            F = I + grad(u)             # Deformation gradient
            Fs = F/(1+beta*phi)
            Bs = Fs*Fs.T
            Js  = det(Fs)
            return 1/(1+beta*phi)*(mu/(Js**(5./3))*(Bs-1./2*tr(Bs)*I)+lmbda*(Js-1)*I)
        u           = Function(U)
        du          = TrialFunction(U)
        F_HE        = inner(sigma_form(u, p_n), E(v))*dx
        J_HE        = derivative(F_HE,u,du)
        problem_HE  = NonlinearVariationalProblem(F_HE, u, bc, J=J_HE,form_compiler_parameters=ffc_options)
        solver_HE   = NonlinearVariationalSolver(problem_HE)
        param_update(solver_HE)
        def mech():
            solver_HE.solve()
            return u
    
    # First iteration solving for displacement, and using the von mises stress field for D
    disp = mech()
    vm   = vonmises(disp)
    D    = project(D0*exp(-gammaD*vm),V)
    #k    = project(k0*exp(-gammaK*vm),V)

    recorder([u,p_n,vm,D,k],['u','p_n','vm','D','k'],name,t)
    
    # Set up reaction-diffusion problem
    dp   = TrialFunction(V)
    p    = Function(V)
    q    = TestFunction(V)
    F_RD = (1/dt)*(p - p_n)*q*dx + D*dot(grad(q),grad(p))*dx - k*p*(1 - p_n)*q*dx  
    J_RD = derivative(F_RD,p) 
    
    # Prepare the solution
    for n in range(num_steps):        
        print("Currently at step "+str(n))
        # Update current time and Compute solution
        t += dt
        problem_RD  = NonlinearVariationalProblem(F_RD, p, J=J_RD,form_compiler_parameters=ffc_options)
        solver_RD   = NonlinearVariationalSolver(problem_RD)
        param_update(solver_RD)
        solver_RD.solve()
        
        # Update previous solution
        p_n.assign(p)
        disp = mech()
        vm   = vonmises(disp)
        D    = project(D0*exp(-gammaD*vm),V)
        #k    = project(k0*exp(-gammaK*vm),V)
        
        recorder([u,p_n,vm,D,k],['u','p_n','vm','D','k'],name,t)
        
    return p
    
#########################################################################
# MAIN 
########################################################################
if __name__ == "__main__":
    # call the function with:
    # python <this file> case r_coeff1 r_coeff2
    if(len(sys.argv) != 7):
        print("wrong number of inputs, should be:\n ")
        print("Syntax: python <this file's name> [0=LE/1=HE] D0 gammaD k0 beta case")
        quit()
    lin_hyp  = int(sys.argv[1])
    D0       = float(sys.argv[2])
    gammaD   = float(sys.argv[3])
    k0       = float(sys.argv[4])
    beta     = float(sys.argv[5])
    case     = sys.argv[6]
                       
    print("lin_hyp = %i, D0 = %f, gammaD = %f, k0 = %f, beta = %f, case = %s\n" % (lin_hyp, D0, gammaD, k0, beta, case))

    t1         = time()
    input_dir  = "../rat-data/rat05/"
    if lin_hyp == 0:
        output_dir = './output/lehe'
    else:
        output_dir = './output/lehe'

    # Prepare a mesh
    mesh = Mesh(input_dir+"gmsh.xml")
    V    = FunctionSpace(mesh, 'CG', 2)
    
    # Model parameters
    t          = 0.
    T          = 1.0              # final time 
    num_steps  = 10              # number of time steps
    dt         = T/num_steps      # time step size
    theta      = 50970.           # carrying capacity - normalize data by this
    mu         = .42              # kPa, bulk shear modulus
    nu         = .45              # poisson's ratio
    lmbda      = 2*mu*nu/(1-2*nu) # lame parameter

    # Load initial tumor condition data
    initial_p = interp(input_dir+"ic.mat","ic")
    initial_p.rename('initial','tumor at day 0')
    
    # Parameters to be optimized
    D0     = Constant(D0)     # mobility or diffusion coefficient
    gammaD = Constant(gammaD)     # initial guess of gamma_D
    beta   = Constant(beta)     # force coefficient for HE
    k0     = Constant(k0)     # growth rate initial guess
    k      = project(k0,V)
    

    # Prepare output file - NEED TO FIX, IT'S ONLY SAVING ONE
    f_notime     = XDMFFile(osjoin(output_dir,'notime'+case+'.xdmf'))
    f_notime.parameters["flush_output"]          = True
    f_notime.parameters["functions_share_mesh"]  = True
    f_notime.parameters["rewrite_function_mesh"] = False

    # run the forward model
    forward(initial_p, case) 
    
    
    
    
