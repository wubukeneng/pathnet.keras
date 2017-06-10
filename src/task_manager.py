from keras.optimizers import SGD
from data_manager import DataManager
from utils import normalize_images
from utils import split_data
from utils import load_layer_weights
from utils import save_layer_weights
from utils import to_categorical
from utils import flatten
from utils import shuffle
from utils import spice_up_images

class TaskManager(object):
    def __init__(self, pathnet, genetic_agents, dataset_name, class_args_list,
                optimizer= SGD(lr=0.0001),
                save_path='../trained_models/',
                max_num_genetic_epochs = 500,
                batch_size=16, num_path_epochs=100,
                num_samples_per_path=16*50
                ):
        self.pathnet = pathnet
        self.genetic_agents = genetic_agents
        self.dataset_name = dataset_name
        self.class_args_list = class_args_list
        self.num_tasks = len(self.class_args_list)
        self.optimizer = optimizer
        self.save_path = save_path
        self.max_num_genetic_epochs = max_num_genetic_epochs
        self.batch_size = batch_size
        self.num_path_epochs = num_path_epochs
        self.verbosity = 0
        self.data_manager = DataManager()
        self.num_samples_per_path = num_samples_per_path

    def _load_data(self, class_args):
        train_data, test_data = self.data_manager.load(self.dataset_name,
                                                        class_args)
        train_data, validation_data = split_data(train_data)
        data_splits = (train_data, validation_data, test_data)
        return data_splits

    def _preprocess_input_data(self, data_splits):
        train_data, validation_data, test_data = data_splits
        train_images, train_classes = train_data
        validation_images, validation_classes = validation_data
        test_images, test_classes = test_data

        # encode outputs into one hot vectors
        class_arg_splits = (train_classes, validation_classes, test_classes)
        categorical_data = [to_categorical(class_arg_split)
                            for class_arg_split in class_arg_splits]
        train_classes, validation_classes, test_classes = categorical_data

        # flatten, add salt/pepper noise and normalize images
        image_splits = (train_images, validation_images, test_images)
        image_splits = [flatten(image_split) for image_split in image_splits]

        image_splits = [spice_up_images(image_split)
                        for image_split in image_splits]

        image_splits = [normalize_images(image_split)
                            for image_split in image_splits]

        train_images, validation_images, test_images = image_splits
        train_data = (train_images, train_classes)
        validation_data = (validation_images, validation_classes)
        test_data = (test_images, test_classes)
        preprocessed_data_split = (train_data, validation_data, test_data)
        return preprocessed_data_split

    def train_tasks(self):
        # train paths with an evolution strategy
        for task_arg in range(self.num_tasks):
            task_classes = self.class_args_list[task_arg]
            task_data_splits = self._load_data(task_classes)
            task_data_splits = self._preprocess_input_data(task_data_splits)
            train_data, validation_data, test_data = task_data_splits
            train_images, train_classes = train_data
            validation_images, validation_classes = validation_data
            chosen_paths = []
            for genetic_epoch_arg in range(self.max_num_genetic_epochs):
                # i am so sorry for this ugly split
                sampled_paths, sampled_args  = \
                            self.genetic_agents.sample_genotype_paths(2)
                train_images, train_classes = shuffle(train_images,
                                                    train_classes)
                sampled_train_images = train_images[:self.num_samples_per_path]
                sampled_train_classes = train_classes[:self.num_samples_per_path]
                print('\n Genetic epoch:', genetic_epoch_arg)
                losses = []
                for genotype_path in sampled_paths:
                    path_model = self.pathnet.build(genotype_path)
                    load_layer_weights(path_model, self.save_path)
                    path_model.compile(optimizer=self.optimizer,
                                loss='categorical_crossentropy',
                                                metrics=['acc'])
                    path_model.fit(sampled_train_images, sampled_train_classes,
                                   self.batch_size, self.num_path_epochs,
                                    self.verbosity, shuffle=True)
                    save_layer_weights(path_model, self.save_path)
                    score = path_model.evaluate(validation_images,
                                                validation_classes,
                                                verbose=self.verbosity)
                    print('\n Loss:', score[0])
                    print('\n Accuracy:', score[1])
                    losses.append(-1 * score[0])
                best_path = genetic_agents.overwrite(sampled_args, losses)
                chosen_paths.append(best_path)


if __name__ == "__main__":
    from genetic_agents import GeneticAgents
    from pathnet import PathNet

    # parameters for genetic agents and path net architecture
    num_layers = 3
    num_modules_per_layer = 10
    num_neurons_per_module = 20
    output_size = 2
    genetic_agents = GeneticAgents(shape=(num_modules_per_layer, num_layers))
    pathnet = PathNet(shape=(num_modules_per_layer, num_layers),
                    num_neurons_per_module=num_neurons_per_module,
                    output_size=output_size)

    # parameters for the task manager
    class_arg_list = [[5, 7]]
    accuracy_treshold = .998
    dataset_name = 'mnist'
    task_manager = TaskManager(pathnet, genetic_agents,
                            dataset_name, class_arg_list)
    task_manager.train_tasks()


